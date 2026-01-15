class BoundingBox:
    def __init__(self, top: int, left: int, bottom: int, right: int):
        self.top = top
        self.left = left
        self.bottom = bottom
        self.right = right

    def __eq__(self, other) -> bool:
        if not isinstance(other, BoundingBox):
            return NotImplemented
        return (
            self.top == other.top
            and self.left == other.left
            and self.bottom == other.bottom
            and self.right == other.right
        )

    @staticmethod
    def unbounded() -> "BoundingBox":
        """An unbounded box, useful to describe an "uncropped" matrix"""
        return BoundingBox(0, 0, -1, -1)
