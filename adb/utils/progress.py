"""进度显示工具."""


class ProgressHandler:
    """进度处理器 — 封装 tqdm，无依赖时回退到简单输出."""

    def __init__(self, total: int = None, desc: str = "Processing",
                 unit: str = "items", enabled: bool = True):
        self.total = total
        self.desc = desc
        self.unit = unit
        self.enabled = enabled
        self._current = 0
        self._tqdm = None

        if enabled:
            try:
                from tqdm import tqdm
                self._tqdm = tqdm(total=total, desc=desc, unit=unit)
            except ImportError:
                pass

    def update(self, n: int = 1):
        """更新进度."""
        self._current += n
        if self._tqdm:
            self._tqdm.update(n)

    def set_description(self, desc: str):
        """更新描述."""
        self.desc = desc
        if self._tqdm:
            self._tqdm.set_description(desc)

    def close(self):
        """关闭进度条."""
        if self._tqdm:
            self._tqdm.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def create_progress(total: int = None, desc: str = "Processing",
                    unit: str = "items", enabled: bool = True) -> ProgressHandler:
    """创建进度处理器的工厂函数.

    Args:
        total: 总步数
        desc: 描述文字
        unit: 单位
        enabled: 是否启用进度显示

    Returns:
        ProgressHandler
    """
    return ProgressHandler(total=total, desc=desc, unit=unit, enabled=enabled)
