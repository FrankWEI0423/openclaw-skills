#!/usr/bin/env python3
"""
石锅王素材库 - Nano Banana (AIsa Gemini) 图片生成脚本
支持：图生图（主力）、进度反馈回调

用法：
  python3 nano_banana_generate.py --mode img2img --ref assets/shiguo_02_700x700.jpg --prompt "提示词" --output output.jpg
  python3 nano_banana_generate.py --mode taobao --output taobao_main.jpg
  python3 nano_banana_generate.py --mode xiaohongshu --output xhs_cover.jpg
  python3 nano_banana_generate.py --mode list
"""

import subprocess, sys, os, json, base64, threading, time
from pathlib import Path

# ============================================================
# 配置区
# ============================================================
AISA_API_KEY = os.environ.get("AISA_API_KEY", "sk-u1fCN653hKQjeLNDtL2zH4srKxWzQbTWmIBMKOKpr0AGRkKg")
AISA_BASE_URL = "api.aisa.one"
AISA_MODEL_PATH = "/v1/models/gemini-3-pro-image-preview:generateContent"

# 飞书配置（用于进度反馈）
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "cli_a9171cb515389bc8")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "8pR8BrMjh8xNVplskfAEBbtshW6HGE0P")
FEISHU_CHAT_ID = os.environ.get("FEISHU_CHAT_ID", "oc_070edbb69256cf350f94b85631d9ed95")

# 素材路径
ASSETS_DIR = Path(__file__).parent.parent / "assets"
SHIGUO_DIR = Path("/root/.openclaw/workspace/assets/shiguo")
# ============================================================


def get_feishu_token():
    """获取飞书 access token"""
    result = subprocess.run([
        "node", "-e", f"""
const https = require('https');
const payload = JSON.stringify({{app_id:'{FEISHU_APP_ID}',app_secret:'{FEISHU_APP_SECRET}'}});
const req = https.request({{hostname:'open.feishu.cn',path:'/open-apis/auth/v3/tenant_access_token/internal',method:'POST',headers:{{'Content-Type':'application/json','Content-Length':Buffer.byteLength(payload)}}}},
  res=>{{let d='';res.on('data',c=>d+=c);res.on('end',()=>{{const r=JSON.parse(d);console.log(r.tenant_access_token)}});}});
req.write(payload);req.end();
"""
    ], capture_output=True, text=True, timeout=10)
    return result.stdout.strip()


def send_feishu_message(text, token=None):
    """发飞书消息（进度反馈用）"""
    try:
        if not token:
            token = get_feishu_token()
        payload = json.dumps({
            "receive_id": FEISHU_CHAT_ID,
            "msg_type": "text",
            "content": json.dumps({"text": text})
        })
        subprocess.run([
            "node", "-e", f"""
const https = require('https');
const payload = {json.dumps(payload)};
const req = https.request({{hostname:'open.feishu.cn',path:'/open-apis/im/v1/messages?receive_id_type=chat_id',method:'POST',headers:{{'Authorization':'Bearer {token}','Content-Type':'application/json','Content-Length':Buffer.byteLength(payload)}}}},
  res=>{{let d='';res.on('data',c=>d+=c);res.on('end',()=>{{console.log('sent')}});}});
req.write(payload);req.end();
"""
        ], capture_output=True, timeout=10)
        print(f"[飞书] {text}")
    except Exception as e:
        print(f"[飞书发送失败] {e}")


class ProgressReporter:
    """每30秒向飞书报告进度"""
    def __init__(self, task_name, feishu_token=None):
        self.task_name = task_name
        self.token = feishu_token
        self.start_time = time.time()
        self.running = False
        self.thread = None

    def start(self):
        self.running = True
        send_feishu_message(f"🎨 开始生成：{self.task_name}，请稍候...", self.token)
        self.thread = threading.Thread(target=self._report_loop, daemon=True)
        self.thread.start()

    def _report_loop(self):
        interval = 30
        while self.running:
            time.sleep(interval)
            if self.running:
                elapsed = int(time.time() - self.start_time)
                send_feishu_message(
                    f"⏳ 正在生成 {self.task_name}，已用时 {elapsed} 秒，请继续等待...",
                    self.token
                )

    def done(self, success=True, output_path=None):
        self.running = False
        elapsed = int(time.time() - self.start_time)
        if success:
            send_feishu_message(f"✅ {self.task_name} 生成完成！用时 {elapsed} 秒。", self.token)
        else:
            send_feishu_message(f"❌ {self.task_name} 生成失败，用时 {elapsed} 秒。", self.token)


def img2img_gemini(ref_image_path, prompt, output_path, task_name="石锅图片", notify_feishu=True):
    """
    核心：用 AIsa Gemini 做图生图
    - ref_image_path: 实物图路径
    - prompt: 英文提示词
    - output_path: 输出路径
    - notify_feishu: 是否每30秒发进度到飞书
    """
    reporter = None
    token = None

    if notify_feishu:
        try:
            token = get_feishu_token()
            reporter = ProgressReporter(task_name, token)
            reporter.start()
        except Exception as e:
            print(f"[进度反馈初始化失败] {e}")

    try:
        # 读取参考图
        with open(ref_image_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode()

        mime_type = "image/png" if str(ref_image_path).endswith(".png") else "image/jpeg"

        # Node.js 调用（绕过 Cloudflare）
        node_script = f"""
const https = require('https');
const fs = require('fs');

const payload = JSON.stringify({{
  contents: [{{ role: "user", parts: [
    {{ inlineData: {{ mimeType: "{mime_type}", data: "{img_b64}" }} }},
    {{ text: {json.dumps(prompt)} }}
  ]}}]
}});

const options = {{
  hostname: '{AISA_BASE_URL}',
  path: '{AISA_MODEL_PATH}',
  method: 'POST',
  headers: {{
    'Authorization': 'Bearer {AISA_API_KEY}',
    'Content-Type': 'application/json',
    'Content-Length': Buffer.byteLength(payload)
  }},
  timeout: 120000
}};

const req = https.request(options, (res) => {{
  let data = '';
  res.on('data', c => data += c);
  res.on('end', () => {{
    try {{
      const result = JSON.parse(data);
      for (const cand of result.candidates || []) {{
        for (const part of cand.content?.parts || []) {{
          const d = part.inlineData || part.inline_data;
          if (d) {{
            const buf = Buffer.from(d.data, 'base64');
            fs.writeFileSync({json.dumps(str(output_path))}, buf);
            console.log('SUCCESS:' + buf.length);
            return;
          }}
          if (part.text) console.log('TEXT:' + part.text.slice(0,200));
        }}
      }}
      console.log('ERROR:no_image:' + JSON.stringify(result).slice(0,200));
    }} catch(e) {{ console.log('ERROR:parse:' + data.slice(0,100)); }}
  }});
}});
req.on('error', e => console.log('ERROR:net:' + e.message));
req.on('timeout', () => {{ req.destroy(); console.log('ERROR:timeout'); }});
req.write(payload);
req.end();
"""
        result = subprocess.run(["node", "-e", node_script], capture_output=True, text=True, timeout=130)
        output = result.stdout.strip()

        if output.startswith("SUCCESS:"):
            size_kb = int(output.split(":")[1]) // 1024
            print(f"✅ 生成成功: {output_path} ({size_kb}KB)")
            if reporter:
                reporter.done(True, output_path)
            return str(output_path)
        else:
            print(f"❌ 生成失败: {output}")
            if reporter:
                reporter.done(False)
            return None

    except Exception as e:
        print(f"❌ 异常: {e}")
        if reporter:
            reporter.done(False)
        return None


def get_best_ref(priority_files):
    """找素材库中最优的参考图"""
    for fname in priority_files:
        for d in [ASSETS_DIR, SHIGUO_DIR]:
            p = d / fname
            if p.exists():
                return str(p)
    return None


def make_taobao_main(output_path="taobao_main.jpg", notify=True):
    """淘宝主图（推荐用 shiguo_02）"""
    ref = get_best_ref(["shiguo_02_700x700.jpg", "shiguo_04_700x700.jpg", "shiguo_01_600x800.jpg"])
    prompt = """Reference photo: real Yunnan steam stone pot (云南蒸汽石锅) with BOTTOM STEAM HOLE (锅底蒸汽孔) — this is the key feature, NOT a top chimney.

Create Taobao main image 1000x1000px. Keep EXACT pot shape.
Dark dramatic background, warm spotlight, steam rising from bottom hole, food inside.
TOP GOLD 3D BOLD: 云南蒸汽石锅
WHITE SUBTITLE: 锅底导汽·天然石蒸·原汁原味
LEFT 4 RED BADGES: 锅底导汽 / 天然原石 / 无涂层 / 厂家直供
BOTTOM RED BANNER: 云南原产地·品质保障·支持定制
TOP RIGHT gold stamp: 正品保障
Premium commercial e-commerce quality."""
    return img2img_gemini(ref, prompt, output_path, "淘宝主图", notify)


def make_xiaohongshu(output_path="xhs_cover.jpg", notify=True):
    """小红书封面（推荐用 shiguo_03，最高清）"""
    ref = get_best_ref(["shiguo_03_1080x1440.jpg", "shiguo_05_960x1280.jpg"])
    prompt = """Reference: real Yunnan steam stone pot. Create Xiaohongshu lifestyle cover 1080x1440px.
Keep exact pot shape. Warm cozy home kitchen scene, steam rising, food inside.
Small gold text: 云南蒸汽石锅·蒸汽养生
Lifestyle photography quality, warm tones, no heavy commercial banners."""
    return img2img_gemini(ref, prompt, output_path, "小红书封面", notify)


def list_assets():
    """列出素材库"""
    found = []
    for d in [ASSETS_DIR, SHIGUO_DIR]:
        if d.exists():
            for ext in ["*.jpg", "*.png", "*.jpeg"]:
                found += sorted(d.glob(ext))
    return [str(p) for p in found]


# ============================================================
# CLI 入口
# ============================================================
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="石锅王图片生成 (Nano Banana / AIsa Gemini)")
    parser.add_argument("--mode", choices=["img2img", "taobao", "xiaohongshu", "list"], default="list")
    parser.add_argument("--ref", help="参考图路径")
    parser.add_argument("--prompt", help="提示词")
    parser.add_argument("--output", default="output.jpg")
    parser.add_argument("--no-notify", action="store_true", help="不发飞书进度")
    args = parser.parse_args()

    notify = not args.no_notify

    if args.mode == "list":
        assets = list_assets()
        print(f"📁 石锅素材库（{len(assets)} 张）：")
        for a in assets:
            print(f"  {a}")

    elif args.mode == "taobao":
        make_taobao_main(args.output, notify)

    elif args.mode == "xiaohongshu":
        make_xiaohongshu(args.output, notify)

    elif args.mode == "img2img":
        if not args.ref or not args.prompt:
            print("❌ 需要 --ref 和 --prompt")
            sys.exit(1)
        img2img_gemini(args.ref, args.prompt, args.output, "自定义图生图", notify)
