import argparse
import sys
import json

from ax_core import check_accessibility_permission
from . import WeWorkService

def main():
    parser = argparse.ArgumentParser(description="企业微信纯无障碍自动发送脚本")
    parser.add_argument("title", nargs="?", default="文件传输助手", help="会话标题")
    parser.add_argument("message", nargs="?", default="独立脚本测试（企微）", help="要发送的消息")
    args = parser.parse_args()

    if not check_accessibility_permission():
        print(json.dumps({"ok": False, "message": "缺少系统辅助功能权限"}, ensure_ascii=False, indent=2))
        return 2

    result = WeWorkService().send_by_title(args.title, args.message)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1

if __name__ == "__main__":
    sys.exit(main())
