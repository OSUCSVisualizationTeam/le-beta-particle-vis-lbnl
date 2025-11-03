class BoundingBox:
    def __init__(self, top: int, left: int, bottom: int, right: int):
        self.top = top
        self.left = left
        self.bottom = bottom
        self.right = right

    @staticmethod
    def unbounded() -> "BoundingBox":
        """An unbounded box, useful to describe an "uncropped" matrix"""
        return BoundingBox(0, 0, -1, -1)
