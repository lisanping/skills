"""建筑构件 — 柱、墙、楼板的参数化定义."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class WallType(Enum):
    EXTERIOR = "exterior"
    INTERIOR = "interior"
    CURTAIN = "curtain"
    FIRE = "fire"


class StructuralMaterial(Enum):
    STEEL = "steel"
    CONCRETE = "concrete"
    WOOD = "wood"
    COMPOSITE = "composite"


class SurfaceFinish(Enum):
    """表面材质效果."""
    MATTE = "matte"         # 哑光 (混凝土、砖石)
    SATIN = "satin"         # 缎面 (木材、涂漆)
    METALLIC = "metallic"   # 金属光泽 (钢、铝)
    GLASS = "glass"         # 玻璃
    GLOSSY = "glossy"       # 高光 (琉璃瓦、抛光石)


@dataclass
class Appearance:
    """构件外观属性 — 颜色、材质、表面效果.

    color_rgb: (R, G, B) 各 0~255; None 时使用默认材质色。
    opacity: 0.0 (全透明) ~ 1.0 (不透明)。
    finish: 表面材质效果。
    """
    color_rgb: tuple[int, int, int] | None = None
    opacity: float = 1.0
    finish: SurfaceFinish = SurfaceFinish.MATTE


# ── 默认外观查找表 ──

DEFAULT_APPEARANCE: dict[str, Appearance] = {
    # 结构材料
    "steel":     Appearance(color_rgb=(192, 192, 200), finish=SurfaceFinish.METALLIC),
    "concrete":  Appearance(color_rgb=(180, 180, 175), finish=SurfaceFinish.MATTE),
    "wood":      Appearance(color_rgb=(180, 140, 100), finish=SurfaceFinish.SATIN),
    "composite": Appearance(color_rgb=(200, 120, 80),  finish=SurfaceFinish.SATIN),
    # 墙体类型
    "exterior":  Appearance(color_rgb=(235, 225, 210), finish=SurfaceFinish.MATTE),   # 米白外墙
    "interior":  Appearance(color_rgb=(245, 242, 235), finish=SurfaceFinish.MATTE),   # 白色内墙
    "fire":      Appearance(color_rgb=(200, 195, 190), finish=SurfaceFinish.MATTE),   # 灰色防火墙
    "curtain":   Appearance(color_rgb=(140, 180, 210), opacity=0.4, finish=SurfaceFinish.GLASS),
    # 楼板
    "slab":      Appearance(color_rgb=(210, 205, 200), finish=SurfaceFinish.MATTE),
    # 玻璃
    "glass":     Appearance(color_rgb=(180, 220, 240), opacity=0.3, finish=SurfaceFinish.GLASS),
    # 屋面
    "roof_tile": Appearance(color_rgb=(120, 100, 80),  finish=SurfaceFinish.SATIN),   # 灰瓦
    "glazed_tile": Appearance(color_rgb=(200, 170, 40), finish=SurfaceFinish.GLOSSY), # 琉璃黄瓦
    # 传统建筑
    "red_wall":  Appearance(color_rgb=(180, 50, 45),   finish=SurfaceFinish.MATTE),   # 红墙
    "marble":    Appearance(color_rgb=(240, 235, 225),  finish=SurfaceFinish.GLOSSY),  # 汉白玉
    "bronze":    Appearance(color_rgb=(140, 120, 80),   finish=SurfaceFinish.METALLIC),# 铜器
}


@dataclass
class Column:
    """结构柱."""

    x: float  # mm
    y: float  # mm
    base_level: str
    top_level: str
    section_width: float = 305.0   # mm
    section_depth: float = 305.0   # mm
    section_thickness: float = 12.0  # mm (方管壁厚)
    material: StructuralMaterial = StructuralMaterial.STEEL
    appearance: Appearance | None = None

    def resolved_appearance(self) -> Appearance:
        return self.appearance or DEFAULT_APPEARANCE.get(self.material.value, DEFAULT_APPEARANCE["steel"])


@dataclass
class Wall:
    """墙体."""

    start: tuple[float, float]  # (x, y) mm
    end: tuple[float, float]
    base_level: str
    top_level: str
    thickness: float = 200.0  # mm
    wall_type: WallType = WallType.INTERIOR
    appearance: Appearance | None = None

    def resolved_appearance(self) -> Appearance:
        return self.appearance or DEFAULT_APPEARANCE.get(self.wall_type.value, DEFAULT_APPEARANCE["exterior"])


@dataclass
class FloorSlab:
    """楼板."""

    level: str
    boundary_points: list[tuple[float, float]]  # 闭合轮廓顶点 (x, y) mm
    thickness: float = 150.0  # mm
    structural: bool = True
    appearance: Appearance | None = None

    def resolved_appearance(self) -> Appearance:
        return self.appearance or DEFAULT_APPEARANCE["slab"]


@dataclass
class Beam:
    """结构梁.

    沿两点定义的中心线生成矩形截面梁体。
    梁底标高 = 所属层标高 - 梁高（梁底挂在楼板下方）。
    """

    start: tuple[float, float]  # (x, y) mm
    end: tuple[float, float]
    level: str                  # 所属标高
    width: float = 300.0        # mm，截面宽
    height: float = 600.0       # mm，截面高
    material: StructuralMaterial = StructuralMaterial.STEEL
    appearance: Appearance | None = None

    def resolved_appearance(self) -> Appearance:
        return self.appearance or DEFAULT_APPEARANCE.get(self.material.value, DEFAULT_APPEARANCE["steel"])


@dataclass
class CurtainWall:
    """幕墙.

    参数化定义幕墙面板：沿 start→end 中心线竖向分割为网格，
    每格为一块玻璃面板，竖梃/横梃按间距自动生成。
    对应案例 TC 13。
    """

    start: tuple[float, float]  # (x, y) mm
    end: tuple[float, float]
    base_level: str
    top_level: str
    panel_width: float = 1500.0     # mm，面板标准宽度
    panel_height: float = 3000.0    # mm，面板标准高度（层高以内）
    mullion_width: float = 60.0     # mm，竖梃宽度
    mullion_depth: float = 120.0    # mm，竖梃进深
    transom_height: float = 50.0    # mm，横梃高度
    transom_depth: float = 100.0    # mm，横梃进深
    glass_thickness: float = 24.0   # mm，中空玻璃厚度
    appearance: Appearance | None = None

    def resolved_appearance(self) -> Appearance:
        return self.appearance or DEFAULT_APPEARANCE["glass"]


@dataclass
class Door:
    """门.

    对应案例 TC 15：办公室门批量放置。
    门在墙上按位置开洞并嵌入门扇。
    """

    host_wall_id: str               # 所属墙体 ID
    position: float                 # 沿墙中心线的比例位置 (0.0~1.0)
    width: float = 900.0            # mm
    height: float = 2100.0          # mm
    door_type: str = "single"       # single / double / sliding
    appearance: Appearance | None = None

    def resolved_appearance(self) -> Appearance:
        return self.appearance or DEFAULT_APPEARANCE["wood"]


@dataclass
class Window:
    """窗户."""

    host_wall_id: str
    position: float                 # 沿墙中心线的比例位置
    width: float = 1500.0           # mm
    height: float = 1800.0          # mm
    sill_height: float = 900.0      # mm，窗台高度
    appearance: Appearance | None = None

    def resolved_appearance(self) -> Appearance:
        return self.appearance or DEFAULT_APPEARANCE["glass"]


class RoofType(Enum):
    """屋顶类型."""
    FLAT = "flat"               # 平屋顶
    GABLE = "gable"             # 硬山/悬山 (两坡)
    HIP = "hip"                 # 庑殿顶 (四坡)
    HALF_HIP = "half_hip"       # 歇山顶 (四坡+两山花)
    CONICAL = "conical"         # 攒尖顶 (锥形, 适用于多边形/圆形平面)


@dataclass
class RoundColumn:
    """圆柱 — 圆形截面柱体.

    相比 Column (矩形方管), RoundColumn 使用圆柱体几何,
    适用于传统建筑木柱、装饰柱、罗马柱等场景。
    """

    x: float  # mm
    y: float  # mm
    base_level: str
    top_level: str
    diameter: float = 400.0         # mm, 柱径
    material: StructuralMaterial = StructuralMaterial.WOOD
    appearance: Appearance | None = None

    def resolved_appearance(self) -> Appearance:
        return self.appearance or DEFAULT_APPEARANCE.get(self.material.value, DEFAULT_APPEARANCE["wood"])


@dataclass
class CurvedRoof:
    """曲面屋顶 — 参数化生成各种传统/现代屋顶.

    通过 roof_type + boundary_points + ridge_height 定义:
    - GABLE/HIP: boundary 为矩形底边, ridge 沿纵向脊线
    - CONICAL: boundary 为多边形底边, ridge_height 为锥尖高度
    - 翘角: overhang + eave_rise 控制檐口上翘

    底面位于 base_level 标高, 脊线位于 base_level + ridge_height。
    """

    base_level: str
    boundary_points: list[tuple[float, float]]  # 屋顶底边轮廓 (mm)
    ridge_height: float = 3000.0                # 脊线高出底面的距离 (mm)
    roof_type: RoofType = RoofType.HIP
    overhang: float = 1500.0                    # 檐口出挑距离 (mm)
    eave_rise: float = 0.0                      # 檐口翘起高度 (mm), 0 = 不翘
    thickness: float = 200.0                    # 屋面厚度 (mm)
    appearance: Appearance | None = None

    def resolved_appearance(self) -> Appearance:
        return self.appearance or DEFAULT_APPEARANCE.get("glazed_tile", DEFAULT_APPEARANCE["roof_tile"])


@dataclass
class Railing:
    """栏杆/勾栏 — 沿路径生成立柱 + 扶手的栏杆系统.

    定义: path (折线点序列) + 立柱间距 + 截面尺寸。
    用于阳台栏杆、台基围栏、楼梯扶手等。
    """

    path_points: list[tuple[float, float]]      # 栏杆路径点 [(x,y), ...] (mm)
    level: str                                   # 所属标高
    height: float = 1100.0                       # 栏杆总高 (mm)
    post_spacing: float = 1500.0                 # 立柱间距 (mm)
    post_width: float = 80.0                     # 立柱截面宽 (mm)
    post_depth: float = 80.0                     # 立柱截面深 (mm)
    rail_width: float = 60.0                     # 扶手截面宽 (mm)
    rail_height: float = 60.0                    # 扶手截面高 (mm)
    bottom_rail: bool = True                     # 是否有底部横杆
    bottom_rail_height: float = 150.0            # 底部横杆高度 (mm)
    material: StructuralMaterial = StructuralMaterial.WOOD
    appearance: Appearance | None = None

    def resolved_appearance(self) -> Appearance:
        return self.appearance or DEFAULT_APPEARANCE.get(self.material.value, DEFAULT_APPEARANCE["wood"])
