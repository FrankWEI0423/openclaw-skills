#!/usr/bin/env python3
"""
石锅王 - Seedream 图生图脚本
用 AISA Seedream 模型，基于实物参考图生成电商主图

用法:
  # 图生图（推荐）
  python3 seedream_img2img.py --ref assets/shiguo_02_700x700.jpg --output output.jpg

  # 纯文生图
  python3 seedream_img2img.py --text-only --output output.jpg

  # 自定义提示词
  python3 seedream_img2img.py --ref assets/shiguo_02_700x700.jpg --prompt "自定义提示词" --output output.jpg
"""

import urllib.request
import json
import base64
import os
import argparse
import time
from pathlib import Path

# 配置
AISA_API_KEY = os.environ.get("AISA_API_KEY", "sk-u1fCN653hKQjeLNDtL2zH4srKxWzQbTWmIBMKOKpr0AGRkKg")
ASSETS_DIR = Path(__file__).parent.parent / "assets"
SHIGUO_DIR = Path("/root/.openclaw/workspace/assets/shiguo")

# 默认提示词（强调锅底只有一个进气孔）
DEFAULT_PROMPT_IMG2IMG = (
    "Professional e-commerce product photo of Yunnan handmade natural stone steam pot. "
    "Keep the exact pot shape from reference image. "
    "The pot has EXACTLY ONE round steam/air intake hole at the CENTER OF THE BOTTOM (not on the side). "
    "White clean background, centered, professional product photography lighting, "
    "sharp focus, high quality commercial photo, 1920x1920"
)

DEFAULT_PROMPT_TEXT2IMG = (
    "Yunnan handmade natural stone steam pot, dark grey rough stone texture, "
    "EXACTLY ONE round steam hole at the bottom center of the pot (not on the side, at the very bottom), "
    "white background, centered, professional e-commerce photography, high quality, 1920x1920"
)


def get_ref_image(ref_path=None):
    """获取参考图，优先用指定路径，否则用素材库最佳图"""
    if ref_path and Path(ref_path).exists():
        return str(ref_path)
    # 优先用 shiguo_02（最清晰的方图）
    candidates = [
        ASSETS_DIR / "shiguo_02_700x700.jpg",
        SHIGUO_DIR / "shiguo_02_700x700.jpg",
        ASSETS_DIR / "shiguo_04_700x700.jpg",
        SHIGUO_DIR / "shiguo_04_700x700.jpg",
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return None


def img2img(ref_path, prompt, output_path, size="1920x1920"):
    """图生图：基于参考图生成"""
    with open(ref_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    body = {
        "model": "seedream-4-5-251128",
        "prompt": prompt,
        "image": f"data:image/jpeg;base64,{img_b64}",
        "n": 1,
        "size": size,
        "response_format": "b64_json"
    }

    headers = {
        "Authorization": f"Bearer {AISA_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "OpenClaw-ShiGuo/1.0"
    }

    print(f"🎨 图生图中（参考: {Path(ref_path).name}）...")
    req = urllib.request.Request(
        "https://api.aisa.one/v1/images/edits",
        data=json.dumps(body).encode(),
        headers=headers
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        resp = json.loads(r.read())

    if resp.get("data"):
        img_data = base64.b64decode(resp["data"][0]["b64_json"])
        with open(output_path, "wb") as f:
            f.write(img_data)
        print(f"✅ 图生图成功！{len(img_data)//1024} KB → {output_path}")
        print(f"MEDIA:{output_path}")
        return output_path
    raise ValueError(f"图生图失败: {resp}")


def text2img(prompt, output_path, size="1920x1920"):
    """纯文生图"""
    body = {
        "model": "seedream-4-5-251128",
        "prompt": prompt,
        "n": 1,
        "size": size,
        "response_format": "b64_json"
    }

    headers = {
        "Authorization": f"Bearer {AISA_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "OpenClaw-ShiGuo/1.0"
    }

    print(f"🎨 文生图中...")
    req = urllib.request.Request(
        "https://api.aisa.one/v1/images/generations",
        data=json.dumps(body).encode(),
        headers=headers
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        resp = json.loads(r.read())

    if resp.get("data"):
        img_data = base64.b64decode(resp["data"][0]["b64_json"])
        with open(output_path, "wb") as f:
            f.write(img_data)
        print(f"✅ 文生图成功！{len(img_data)//1024} KB → {output_path}")
        print(f"MEDIA:{output_path}")
        return output_path
    raise ValueError(f"文生图失败: {resp}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="石锅王 Seedream 图片生成")
    parser.add_argument("--ref", help="参考图路径（图生图模式）")
    parser.add_argument("--prompt", help="自定义提示词")
    parser.add_argument("--output", default=f"shiguo_{int(time.time())}.jpg", help="输出路径")
    parser.add_argument("--size", default="1920x1920", help="尺寸")
    parser.add_argument("--text-only", action="store_true", help="纯文生图模式")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)

    if args.text_only:
        prompt = args.prompt or DEFAULT_PROMPT_TEXT2IMG
        text2img(prompt, args.output, args.size)
    else:
        ref = get_ref_image(args.ref)
        if not ref:
            print("⚠️  未找到参考图，切换为文生图模式")
            prompt = args.prompt or DEFAULT_PROMPT_TEXT2IMG
            text2img(prompt, args.output, args.size)
        else:
            prompt = args.prompt or DEFAULT_PROMPT_IMG2IMG
            img2img(ref, prompt, args.output, args.size)
