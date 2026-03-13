import re

with open('cleaner.py', 'r', encoding='utf-8') as f:
    content = f.read()

pattern = re.compile(r'self\.prog\.start\(12\).*?elif t == "dir":\n\s*shutil\.rmtree\(item\["path"\]\)\n\s*self\._log\(f"  ... 删除目录：\{item\[\'path\'\]\}", "ok"\)\n\s*', re.DOTALL)

replacement = r'''self.prog.start(12)
        self._status.set("正在清理")
        threading.Thread(target=self._clean_thread, daemon=True).start()

    def _delete_reg_key_tree(self, hive, subkey):
        try:
            with winreg.OpenKey(hive, subkey, 0, winreg.KEY_ALL_ACCESS) as key:
                while True:
                    try:
                        sub = winreg.EnumKey(key, 0)
                        self._delete_reg_key_tree(hive, f"{subkey}\\{sub}")
                    except OSError:
                        break
            winreg.DeleteKey(hive, subkey)
        except Exception as e:
            raise e

    def _remove_readonly(self, func, path, exc_info):
        try:
            import stat
            import os
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception:
            pass

    def _clean_thread(self):
        self._log_sep()
        self._log("=== 开始执行清理 ===", "info")
        errors = []
        for item in list(self._items_to_clean):
            try:
                t = item["type"]
                if t == "file":
                    os.remove(item["path"])
                    self._log(f"   删除文件：{item['path']}", "ok")
                elif t == "dir":
                    shutil.rmtree(item["path"], onerror=self._remove_readonly)
                    self._log(f"   删除目录：{item['path']}", "ok")
                '''

new_content = pattern.sub(replacement, content, count=1)

with open('cleaner.py', 'w', encoding='utf-8') as f:
    f.write(new_content)
