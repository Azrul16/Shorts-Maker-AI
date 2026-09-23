"""Draw the simple application icon using Qt vector primitives."""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QImage, QPainter, QColor, QPolygonF, QPen

image = QImage(256, 256, QImage.Format.Format_ARGB32)
image.fill(Qt.GlobalColor.transparent)
p = QPainter(image)
p.setRenderHint(QPainter.RenderHint.Antialiasing)
p.setPen(Qt.PenStyle.NoPen)
p.setBrush(QColor("#111b2d"))
p.drawRoundedRect(0, 0, 256, 256, 54, 54)
p.setPen(QPen(QColor("#63e5c2"), 12))
p.setBrush(Qt.BrushStyle.NoBrush)
p.drawRoundedRect(68, 32, 120, 192, 20, 20)
p.setPen(Qt.PenStyle.NoPen)
p.setBrush(QColor("#63e5c2"))
p.drawPolygon(QPolygonF([QPointF(105, 91), QPointF(105, 165), QPointF(157, 128)]))
p.end()
assert image.save("assets/app.ico"), "Could not save icon"
