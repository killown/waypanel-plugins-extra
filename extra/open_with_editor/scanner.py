def get_scanner_logic():
    import os
    import fnmatch

    class FileScanner:
        def __init__(self, plugin):
            self.p = plugin

        def load_gitignore(self, directory):
            path = os.path.join(directory, ".gitignore")
            patterns = []
            if os.path.exists(path):
                try:
                    with open(path, "r") as f:
                        patterns = [
                            l.strip() for l in f if l.strip() and not l.startswith("#")
                        ]
                except Exception as e:
                    self.p.logger.warning(f"Error reading .gitignore: {e}")
            return patterns

        def is_ignored(self, relative_path, patterns):
            for pattern in patterns:
                if fnmatch.fnmatch(relative_path, pattern):
                    return True
                if fnmatch.fnmatch(os.path.basename(relative_path), pattern):
                    return True
                if pattern.endswith("/") and fnmatch.fnmatch(
                    relative_path + "/", pattern
                ):
                    return True
            return False

        def get_files(self, directory):
            if directory in self.p.cached_files:
                return self.p.cached_files[directory]

            files = []
            if not os.path.isdir(directory):
                return files

            patterns = self.load_gitignore(directory)
            for root, dirnames, filenames in os.walk(directory):
                rel_root = os.path.relpath(root, directory)
                if rel_root == ".":
                    rel_root = ""

                dirnames[:] = [
                    d
                    for d in dirnames
                    if not d.startswith(".")
                    and not self.is_ignored(os.path.join(rel_root, d), patterns)
                ]

                for f in filenames:
                    if f.startswith("."):
                        continue
                    rel_f = os.path.join(rel_root, f)
                    if not self.is_ignored(rel_f, patterns):
                        files.append(os.path.join(root, f))

            self.p.cached_files[directory] = files
            return files

    return FileScanner
