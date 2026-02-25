#!/usr/bin/env python3
"""
石锅王素材库 - 图片保存脚本
用法：当用户在飞书群发图片并说"存到石锅素材库"时执行

从飞书消息中下载图片并保存到石锅素材库
"""

import urllib.request
import json
import os
import sys
from datetime import datetime

# 配置
SAVE_DIR = "/root/.openclaw/workspace/assets/shiguo"
FEISHU_APP_ID = "cli_a917189784785bde"
FEISHU_APP_SECRET = "KHmqi0iB6XgdZzxYPagjsdhIWQSWvchs"


def get_feishu_token():
    """获取飞书访问Token"""
    data = json.dumps({
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    }).encode()
    req = urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read()).get("tenant_access_token", "")


def download_image(token, message_id, img_key, save_path):
    """从飞书消息下载图片"""
    url = f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/resources/{img_key}?type=image"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as r:
        content = r.read()
        with open(save_path, "wb") as f:
            f.write(content)
        return len(content)


def save_images(message_id, img_keys, category=""):
    """
    保存多张图片到素材库
    
    Args:
        message_id: 飞书消息ID
        img_keys: 图片key列表
        category: 分类子目录（可选，如"产品细节"、"使用场景"）
    """
    token = get_feishu_token()
    
    # 确定保存目录
    if category:
        save_dir = os.path.join(SAVE_DIR, category)
    else:
        save_dir = SAVE_DIR
    os.makedirs(save_dir, exist_ok=True)
    
    # 获取现有图片数量（用于编号）
    existing = [f for f in os.listdir(SAVE_DIR) if f.endswith('.jpg') and f.startswith('shiguo_')]
    start_num = len(existing) + 1
    
    results = []
    for i, img_key in enumerate(img_keys):
        num = start_num + i
        filename = f"shiguo_{num:02d}.jpg"
        save_path = os.path.join(save_dir, filename)
        
        try:
            size = download_image(token, message_id, img_key, save_path)
            results.append(f"✅ {filename} ({size/1024:.1f} KB)")
            print(f"✅ 保存: {filename} ({size/1024:.1f} KB)")
        except Exception as e:
            results.append(f"❌ 第{num}张失败: {e}")
            print(f"❌ 第{num}张失败: {e}")
    
    # 更新 README 时间戳
    readme_path = os.path.join(SAVE_DIR, "README.md")
    if os.path.exists(readme_path):
        with open(readme_path, "r") as f:
            content = f.read()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        # 在文件末尾追加更新记录
        with open(readme_path, "a") as f:
            f.write(f"\n### 更新记录 {timestamp}\n")
            for r in results:
                f.write(f"- {r}\n")
    
    return results


if __name__ == "__main__":
    # 示例用法
    if len(sys.argv) < 3:
        print("用法: python3 save_shiguo_image.py <message_id> <img_key1> [img_key2 ...] [--category 分类名]")
        sys.exit(1)
    
    args = sys.argv[1:]
    category = ""
    
    if "--category" in args:
        cat_idx = args.index("--category")
        category = args[cat_idx + 1]
        args = [a for a in args if a != "--category" and a != category]
    
    message_id = args[0]
    img_keys = args[1:]
    
    results = save_images(message_id, img_keys, category)
    print("\n完成！")
    for r in results:
        print(r)
