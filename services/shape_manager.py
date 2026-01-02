"""
Shape Manager Service.

Manages shape definitions for node visualization in the canvas and palette.
Handles loading default shapes, merging user customizations, and saving changes.

Usage:
    manager = ShapeManager.instance()
    manager.initialize()  # Call once at startup
    
    shape = manager.get_shape("HOST")
    manager.update_shape(modified_shape)
"""

import math
from pathlib import Path
from typing import Dict, Optional, List, Any
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtGui import QPainterPath, QTransform
from PyQt6.QtCore import QRectF, QPointF

from models.shape_definition import (
    ShapeDefinition, ShapePrimitive, ShapeConnector, ShapeStyle,
    ControlPoint, Edge, ShapeLibrary,
    PrimitiveType, PointType, EdgeType,
)
from models.network import NodeType
from models.grid_nodes import GridNodeType


class ShapeManager(QObject):
    """
    Singleton service managing shape definitions.
    
    Handles:
    - Loading defaults + user overrides at startup
    - Computing union of primitives → QPainterPath
    - Caching paths for performance
    - Saving user modifications
    - Emitting change signals
    
    Signals:
        shapeChanged(str): Emitted when a shape is modified (shape_id)
        shapeAdded(str): Emitted when a new shape is added (shape_id)
        shapeRemoved(str): Emitted when a shape is removed (shape_id)
        allShapesReloaded(): Emitted when all shapes are reloaded
    """
    
    # Signals
    shapeChanged = pyqtSignal(str)
    shapeAdded = pyqtSignal(str)
    shapeRemoved = pyqtSignal(str)
    allShapesReloaded = pyqtSignal()
    
    _instance: Optional['ShapeManager'] = None
    
    @classmethod
    def instance(cls) -> 'ShapeManager':
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    @classmethod
    def reset_instance(cls):
        """Reset the singleton (for testing)."""
        cls._instance = None
    
    def __init__(self):
        super().__init__()
        self._shapes: Dict[str, ShapeDefinition] = {}
        self._path_cache: Dict[str, QPainterPath] = {}
        self._shapes_dir: Path = Path.home() / ".ns3gui" / "shapes"
        self._initialized = False
    
    @property
    def shapes_directory(self) -> Path:
        """Get the shapes directory path."""
        return self._shapes_dir
    
    @shapes_directory.setter
    def shapes_directory(self, path: Path):
        """Set the shapes directory path."""
        self._shapes_dir = Path(path)
    
    def initialize(self):
        """
        Initialize the shape manager.
        
        Loads default shapes, then overlays any user customizations.
        Should be called once at application startup.
        """
        if self._initialized:
            return
        
        self._ensure_shapes_directory()
        self._load_default_shapes()
        self._load_user_shapes()
        self._initialized = True
    
    def _ensure_shapes_directory(self):
        """Create shapes directory if it doesn't exist."""
        self._shapes_dir.mkdir(parents=True, exist_ok=True)
        exports_dir = self._shapes_dir / "exports"
        exports_dir.mkdir(exist_ok=True)
    
    def _load_default_shapes(self):
        """Load built-in default shapes for all node types."""
        # Standard node types
        for node_type in NodeType:
            shape = self._create_default_shape_for_standard(node_type)
            self._shapes[node_type.name] = shape
        
        # Grid node types
        for grid_type in GridNodeType:
            shape = self._create_default_shape_for_grid(grid_type)
            self._shapes[grid_type.name] = shape
    
    def _load_user_shapes(self):
        """Load user customizations from file."""
        user_file = self._shapes_dir / "user_shapes.json"
        if user_file.exists():
            library = ShapeLibrary.load_from_file(user_file)
            if library:
                # Merge user shapes, overwriting defaults
                for shape_id, shape in library.shapes.items():
                    shape.is_default = False
                    self._shapes[shape_id] = shape
                print(f"Loaded {len(library.shapes)} user shape customizations")
    
    def _save_user_shapes(self):
        """Save user-modified shapes to file."""
        # Collect only modified shapes
        library = ShapeLibrary()
        for shape_id, shape in self._shapes.items():
            if shape.modified and not shape.is_default:
                library.add_shape(shape)
        
        if library.shapes:
            user_file = self._shapes_dir / "user_shapes.json"
            library.save_to_file(user_file)
            print(f"Saved {len(library.shapes)} user shape customizations")
    
    # =========================================================================
    # Public API
    # =========================================================================
    
    def get_shape(self, shape_id: str) -> Optional[ShapeDefinition]:
        """
        Get a shape definition by ID.
        
        Args:
            shape_id: Shape identifier (e.g., "HOST", "RTU", "CONTROL_CENTER")
            
        Returns:
            ShapeDefinition or None if not found
        """
        if not self._initialized:
            self.initialize()
        return self._shapes.get(shape_id)
    
    def get_all_shapes(self) -> Dict[str, ShapeDefinition]:
        """Get all registered shapes."""
        if not self._initialized:
            self.initialize()
        return self._shapes.copy()
    
    def get_shape_ids(self) -> List[str]:
        """Get list of all shape IDs."""
        if not self._initialized:
            self.initialize()
        return list(self._shapes.keys())
    
    def update_shape(self, shape: ShapeDefinition):
        """
        Update a shape definition and save to user file.
        
        Args:
            shape: Modified shape definition
        """
        shape.modified = True
        shape.is_default = False
        self._shapes[shape.id] = shape
        self._invalidate_cache(shape.id)
        self._save_user_shapes()
        self.shapeChanged.emit(shape.id)
    
    def reset_shape_to_default(self, shape_id: str) -> bool:
        """
        Reset a shape to its default definition.
        
        Args:
            shape_id: Shape identifier
            
        Returns:
            True if reset, False if shape not found
        """
        # Try to find default for standard node type
        try:
            node_type = NodeType[shape_id]
            default_shape = self._create_default_shape_for_standard(node_type)
            self._shapes[shape_id] = default_shape
            self._invalidate_cache(shape_id)
            self._save_user_shapes()
            self.shapeChanged.emit(shape_id)
            return True
        except KeyError:
            pass
        
        # Try grid node type
        try:
            grid_type = GridNodeType[shape_id]
            default_shape = self._create_default_shape_for_grid(grid_type)
            self._shapes[shape_id] = default_shape
            self._invalidate_cache(shape_id)
            self._save_user_shapes()
            self.shapeChanged.emit(shape_id)
            return True
        except KeyError:
            pass
        
        return False
    
    def add_custom_shape(self, shape: ShapeDefinition):
        """
        Add a new custom shape.
        
        Args:
            shape: New shape definition
        """
        shape.is_default = False
        shape.modified = True
        self._shapes[shape.id] = shape
        self._save_user_shapes()
        self.shapeAdded.emit(shape.id)
    
    def remove_shape(self, shape_id: str) -> bool:
        """
        Remove a shape (only non-default shapes can be removed).
        
        Args:
            shape_id: Shape identifier
            
        Returns:
            True if removed, False if not found or is default
        """
        shape = self._shapes.get(shape_id)
        if shape and not shape.is_default:
            del self._shapes[shape_id]
            self._invalidate_cache(shape_id)
            self._save_user_shapes()
            self.shapeRemoved.emit(shape_id)
            return True
        return False
    
    # =========================================================================
    # Path Computation
    # =========================================================================
    
    def get_unified_path(self, shape_id: str, width: float, height: float) -> QPainterPath:
        """
        Get the unified QPainterPath for a shape, scaled to given dimensions.
        
        Uses caching for performance. The path is computed by unioning all
        primitives in the shape definition.
        
        Args:
            shape_id: Shape identifier
            width: Target width in pixels
            height: Target height in pixels
            
        Returns:
            QPainterPath representing the shape
        """
        if not self._initialized:
            self.initialize()
        
        cache_key = f"{shape_id}_{width:.1f}_{height:.1f}"
        if cache_key not in self._path_cache:
            shape = self._shapes.get(shape_id)
            if shape:
                self._path_cache[cache_key] = self._compute_unified_path(shape, width, height)
            else:
                self._path_cache[cache_key] = self._default_ellipse_path(width, height)
        return self._path_cache[cache_key]
    
    def _invalidate_cache(self, shape_id: str):
        """Clear cached paths for a shape."""
        keys_to_remove = [k for k in self._path_cache if k.startswith(f"{shape_id}_")]
        for k in keys_to_remove:
            del self._path_cache[k]
    
    def clear_cache(self):
        """Clear all cached paths."""
        self._path_cache.clear()
    
    def _compute_unified_path(self, shape: ShapeDefinition, w: float, h: float) -> QPainterPath:
        """
        Compute union of all primitives into single path.
        
        Uses QPainterPath.united() for CSG union operation.
        """
        if not shape.primitives:
            return self._default_ellipse_path(w, h)
        
        # Build path for each primitive
        paths = []
        for prim in shape.primitives:
            path = self._primitive_to_path(prim, w, h)
            if not path.isEmpty():
                paths.append(path)
        
        if not paths:
            return self._default_ellipse_path(w, h)
        
        # Union all paths together
        result = paths[0]
        for path in paths[1:]:
            result = result.united(path)
        
        return result
    
    def calculate_path_start_offset(self, shape: ShapeDefinition, 
                                     width: float = None, height: float = None) -> float:
        """
        Calculate the offset needed to align 0% with 3 o'clock position.
        
        This finds where the rightmost point (at vertical center) is on the path
        and returns that as a percentage offset. When applied:
        - qt_percent = (edge_position + offset) % 1.0
        - edge_position = (qt_percent - offset) % 1.0
        
        Args:
            shape: The shape definition
            width: Width for path computation (uses base_width if not specified)
            height: Height for path computation (uses base_height if not specified)
            
        Returns:
            Offset value from 0.0 to 1.0
        """
        w = width or shape.base_width
        h = height or shape.base_height
        
        path = self._compute_unified_path(shape, w, h)
        if path.isEmpty():
            return 0.0
        
        # Find the point closest to right-center (3 o'clock position)
        # For a shape centered at (w/2, h/2), right-center is at (w, h/2)
        target_x = w
        target_y = h / 2
        
        best_t = 0.0
        best_dist = float('inf')
        
        # Coarse search
        for i in range(100):
            t = i / 100.0
            pt = path.pointAtPercent(t)
            dist = (pt.x() - target_x)**2 + (pt.y() - target_y)**2
            if dist < best_dist:
                best_dist = dist
                best_t = t
        
        # Fine search around best_t
        for i in range(-10, 11):
            t = (best_t + i / 1000.0) % 1.0
            if t < 0:
                t += 1.0
            pt = path.pointAtPercent(t)
            dist = (pt.x() - target_x)**2 + (pt.y() - target_y)**2
            if dist < best_dist:
                best_dist = dist
                best_t = t
        
        return best_t
    
    def update_shape_path_offset(self, shape: ShapeDefinition):
        """
        Recalculate and update the path_start_offset for a shape.
        
        Call this after modifying shape primitives to keep the offset current.
        """
        shape.path_start_offset = self.calculate_path_start_offset(shape)
    
    def _primitive_to_path(self, prim: ShapePrimitive, w: float, h: float) -> QPainterPath:
        """Convert a single primitive to QPainterPath."""
        path = QPainterPath()
        
        if prim.primitive_type == PrimitiveType.ELLIPSE:
            x, y, pw, ph = prim.bounds
            rect = QRectF(x * w, y * h, pw * w, ph * h)
            
            if prim.rotation != 0:
                # Create ellipse at origin, rotate, then translate
                temp_path = QPainterPath()
                temp_path.addEllipse(QRectF(-pw * w / 2, -ph * h / 2, pw * w, ph * h))
                
                transform = QTransform()
                transform.translate((x + pw / 2) * w, (y + ph / 2) * h)
                transform.rotate(prim.rotation)
                path = transform.map(temp_path)
            else:
                path.addEllipse(rect)
                
        elif prim.primitive_type == PrimitiveType.RECTANGLE:
            x, y, pw, ph = prim.bounds
            rect = QRectF(x * w, y * h, pw * w, ph * h)
            
            if prim.corner_radius > 0:
                # Corner radius is normalized to min dimension
                r = prim.corner_radius * min(pw * w, ph * h)
                path.addRoundedRect(rect, r, r)
            else:
                path.addRect(rect)
                
            if prim.rotation != 0:
                transform = QTransform()
                center = rect.center()
                transform.translate(center.x(), center.y())
                transform.rotate(prim.rotation)
                transform.translate(-center.x(), -center.y())
                path = transform.map(path)
                
        elif prim.primitive_type == PrimitiveType.POLYGON:
            if prim.points:
                path.moveTo(prim.points[0].x * w, prim.points[0].y * h)
                for pt in prim.points[1:]:
                    path.lineTo(pt.x * w, pt.y * h)
                if prim.closed:
                    path.closeSubpath()
                    
        elif prim.primitive_type == PrimitiveType.PATH:
            path = self._build_bezier_path(prim, w, h)
            
        return path
    
    def _build_bezier_path(self, prim: ShapePrimitive, w: float, h: float) -> QPainterPath:
        """Build path with bezier curves from points and edges."""
        path = QPainterPath()
        if not prim.points:
            return path
        
        points_dict = {p.id: p for p in prim.points}
        
        # If no edges defined, auto-connect points in order
        if not prim.edges:
            path.moveTo(prim.points[0].x * w, prim.points[0].y * h)
            for pt in prim.points[1:]:
                path.lineTo(pt.x * w, pt.y * h)
            if prim.closed:
                path.closeSubpath()
            return path
        
        # Process explicit edges
        # Find starting point
        first_edge = prim.edges[0]
        start = points_dict.get(first_edge.start_point_id)
        if start:
            path.moveTo(start.x * w, start.y * h)
        
        for edge in prim.edges:
            end = points_dict.get(edge.end_point_id)
            if not end:
                continue
            
            if edge.edge_type == EdgeType.LINE:
                path.lineTo(end.x * w, end.y * h)
                
            elif edge.edge_type == EdgeType.QUADRATIC:
                if edge.control1:
                    cx, cy = edge.control1
                    path.quadTo(cx * w, cy * h, end.x * w, end.y * h)
                else:
                    path.lineTo(end.x * w, end.y * h)
                    
            elif edge.edge_type == EdgeType.CUBIC:
                if edge.control1 and edge.control2:
                    c1x, c1y = edge.control1
                    c2x, c2y = edge.control2
                    path.cubicTo(c1x * w, c1y * h, c2x * w, c2y * h, end.x * w, end.y * h)
                elif edge.control1:
                    cx, cy = edge.control1
                    path.quadTo(cx * w, cy * h, end.x * w, end.y * h)
                else:
                    path.lineTo(end.x * w, end.y * h)
                    
            elif edge.edge_type == EdgeType.ARC:
                # Approximate arc with bezier
                path.lineTo(end.x * w, end.y * h)
        
        if prim.closed:
            path.closeSubpath()
        
        return path
    
    def _default_ellipse_path(self, w: float, h: float) -> QPainterPath:
        """Create a default ellipse path as fallback."""
        path = QPainterPath()
        path.addEllipse(QRectF(0, 0, w, h))
        return path
    
    # =========================================================================
    # Connector Position Computation
    # =========================================================================
    
    def get_connector_position(self, shape_id: str, connector_id: str,
                                width: float, height: float) -> tuple:
        """
        Get connector position and angle on the shape edge.
        
        Args:
            shape_id: Shape identifier
            connector_id: Connector identifier
            width: Shape width in pixels
            height: Shape height in pixels
            
        Returns:
            Tuple of (x, y, angle_degrees) where angle is the outward normal
        """
        shape = self._shapes.get(shape_id)
        if not shape:
            return (width / 2, 0, 270)  # Default top center
        
        path = self.get_unified_path(shape_id, width, height)
        
        for conn in shape.connectors:
            if conn.id == connector_id:
                return self._compute_connector_position(path, conn.edge_position)
        
        return (width / 2, 0, 270)
    
    def get_all_connector_positions(self, shape_id: str, width: float, height: float) -> List[tuple]:
        """
        Get positions for all connectors on a shape.
        
        Args:
            shape_id: Shape identifier
            width: Shape width in pixels
            height: Shape height in pixels
            
        Returns:
            List of (connector_id, x, y, angle_degrees) tuples
        """
        shape = self._shapes.get(shape_id)
        if not shape:
            return []
        
        path = self.get_unified_path(shape_id, width, height)
        
        result = []
        for conn in shape.connectors:
            x, y, angle = self._compute_connector_position(path, conn.edge_position)
            result.append((conn.id, conn.label, x, y, angle))
        
        return result
    
    def edge_to_qt_percent(self, edge_position: float, path_start_offset: float) -> float:
        """Convert edge_position (angular) to Qt path percent.
        
        Args:
            edge_position: Position in our coordinate system (0 = 3 o'clock)
            path_start_offset: Offset for this shape's path
            
        Returns:
            Qt path percent (0-1)
        """
        qt_percent = (edge_position + path_start_offset) % 1.0
        if qt_percent < 0:
            qt_percent += 1.0
        return qt_percent
    
    def qt_percent_to_edge(self, qt_percent: float, path_start_offset: float) -> float:
        """Convert Qt path percent to edge_position (angular).
        
        Args:
            qt_percent: Qt path percent (0-1)
            path_start_offset: Offset for this shape's path
            
        Returns:
            edge_position in our coordinate system (0 = 3 o'clock)
        """
        edge_position = (qt_percent - path_start_offset) % 1.0
        if edge_position < 0:
            edge_position += 1.0
        return edge_position
    
    def _compute_connector_position(self, path: QPainterPath, edge_position: float,
                                     path_start_offset: float = 0.0) -> tuple:
        """Compute position and angle for a connector on a path.
        
        Coordinate system:
        - 0% / 0 rad = right (3 o'clock)
        - 25% / π/2 rad = bottom (6 o'clock)
        - 50% / π rad = left (9 o'clock)
        - 75% / 3π/2 rad = top (12 o'clock)
        
        Args:
            path: The QPainterPath
            edge_position: Position in our angular coordinate system (0 = 3 o'clock)
            path_start_offset: Offset to align path with coordinate system
            
        Returns:
            Tuple of (x, y, normal_angle)
        """
        # Apply offset to convert to Qt path percent
        qt_percent = self.edge_to_qt_percent(edge_position, path_start_offset)
        point = path.pointAtPercent(qt_percent)
        # Get tangent angle
        angle = path.angleAtPercent(qt_percent)
        # Normal points outward (perpendicular to tangent)
        normal_angle = (angle + 90) % 360
        return (point.x(), point.y(), normal_angle)
    
    def snap_to_edge(self, shape_id: str, x: float, y: float,
                     width: float, height: float) -> tuple:
        """
        Snap a point to the nearest position on the shape edge.
        
        Used when dragging connectors.
        
        Args:
            shape_id: Shape identifier
            x: X coordinate to snap
            y: Y coordinate to snap
            width: Shape width in pixels
            height: Shape height in pixels
            
        Returns:
            Tuple of (edge_position, snapped_x, snapped_y)
            edge_position uses our coordinate system: 0% = right (3 o'clock)
        """
        shape = self._shapes.get(shape_id)
        path_start_offset = shape.path_start_offset if shape else 0.0
        
        path = self.get_unified_path(shape_id, width, height)
        
        # Binary search for closest point on path (in Qt percent)
        best_qt_t = 0.0
        best_dist = float('inf')
        
        # Coarse search
        for i in range(101):
            t = i / 100.0
            pt = path.pointAtPercent(t)
            dist = (pt.x() - x) ** 2 + (pt.y() - y) ** 2
            if dist < best_dist:
                best_dist = dist
                best_qt_t = t
        
        # Fine search around best_qt_t
        for i in range(-10, 11):
            t = max(0, min(1, best_qt_t + i / 1000.0))
            pt = path.pointAtPercent(t)
            dist = (pt.x() - x) ** 2 + (pt.y() - y) ** 2
            if dist < best_dist:
                best_dist = dist
                best_qt_t = t
        
        final_pt = path.pointAtPercent(best_qt_t)
        
        # Convert Qt percent to our edge_position
        edge_position = self.qt_percent_to_edge(best_qt_t, path_start_offset)
        
        return (edge_position, final_pt.x(), final_pt.y())
    
    # =========================================================================
    # Export/Import
    # =========================================================================
    
    def export_shape(self, shape_id: str, filepath: Path) -> bool:
        """Export a single shape to a JSON file."""
        shape = self._shapes.get(shape_id)
        if shape:
            return shape.save_to_file(filepath)
        return False
    
    def import_shape(self, filepath: Path) -> Optional[str]:
        """
        Import a shape from a JSON file.
        
        Returns:
            Shape ID if successful, None otherwise
        """
        shape = ShapeDefinition.load_from_file(filepath)
        if shape:
            shape.is_default = False
            shape.modified = True
            self._shapes[shape.id] = shape
            self._save_user_shapes()
            self.shapeAdded.emit(shape.id)
            return shape.id
        return None
    
    def export_all_shapes(self, filepath: Path) -> bool:
        """Export all shapes to a library file."""
        library = ShapeLibrary()
        for shape_id, shape in self._shapes.items():
            library.add_shape(shape)
        return library.save_to_file(filepath)
    
    # =========================================================================
    # Default Shape Creation
    # =========================================================================
    
    def _create_default_shape_for_standard(self, node_type: NodeType) -> ShapeDefinition:
        """Create default shape for a standard node type."""
        
        # Colors matching the palette
        COLORS = {
            NodeType.HOST: ("#4A90D9", "#2563EB"),
            NodeType.ROUTER: ("#7B68EE", "#5B4CD9"),
            NodeType.SWITCH: ("#50C878", "#3DA662"),
            NodeType.STATION: ("#FF9500", "#D97E00"),
            NodeType.ACCESS_POINT: ("#FF3B30", "#D92D24"),
        }
        
        ICONS = {
            NodeType.HOST: "H",
            NodeType.ROUTER: "R",
            NodeType.SWITCH: "S",
            NodeType.STATION: "📶",
            NodeType.ACCESS_POINT: "AP",
        }
        
        fill_color, stroke_color = COLORS.get(node_type, ("#4A90D9", "#2563EB"))
        icon_text = ICONS.get(node_type, "?")
        
        # All standard nodes use ellipse shape
        primitive = ShapePrimitive.create_ellipse()
        
        # Standard 4 connectors at cardinal directions
        # Coordinate system: 0% = right (3 o'clock), increases clockwise
        connectors = [
            ShapeConnector(edge_position=0.0, label="E"),    # Right (3 o'clock)
            ShapeConnector(edge_position=0.25, label="S"),   # Bottom (6 o'clock)
            ShapeConnector(edge_position=0.5, label="W"),    # Left (9 o'clock)
            ShapeConnector(edge_position=0.75, label="N"),   # Top (12 o'clock)
        ]
        
        style = ShapeStyle(
            fill_color=fill_color,
            stroke_color=stroke_color,
            stroke_width=2.0,
            icon_text=icon_text,
            icon_font_size=16,
            icon_color="#FFFFFF",
            icon_bold=True,
        )
        
        shape = ShapeDefinition(
            id=node_type.name,
            name=node_type.name.replace("_", " ").title(),
            primitives=[primitive],
            connectors=connectors,
            style=style,
            base_width=50.0,
            base_height=50.0,
            is_default=True,
            modified=False,
        )
        
        # Calculate and store the path start offset
        shape.path_start_offset = self.calculate_path_start_offset(shape)
        
        return shape
    
    def _create_default_shape_for_grid(self, grid_type: GridNodeType) -> ShapeDefinition:
        """Create default shape for a grid node type."""
        
        # Colors matching the grid palette
        COLORS = {
            # Control hierarchy - Blue tones
            GridNodeType.CONTROL_CENTER: ("#1E40AF", "#1E3A8A"),
            GridNodeType.BACKUP_CONTROL_CENTER: ("#3B82F6", "#2563EB"),
            # Substation equipment - Green/Teal tones
            GridNodeType.SUBSTATION: ("#065F46", "#064E3B"),
            GridNodeType.RTU: ("#059669", "#047857"),
            GridNodeType.IED: ("#10B981", "#059669"),
            GridNodeType.DATA_CONCENTRATOR: ("#34D399", "#10B981"),
            GridNodeType.RELAY: ("#6EE7B7", "#34D399"),
            GridNodeType.METER: ("#A7F3D0", "#6EE7B7"),
            # Communication infrastructure - Purple/Orange tones
            GridNodeType.GATEWAY: ("#7C3AED", "#6D28D9"),
            GridNodeType.COMM_ROUTER: ("#8B5CF6", "#7C3AED"),
            GridNodeType.COMM_SWITCH: ("#A78BFA", "#8B5CF6"),
            GridNodeType.COMM_TOWER: ("#F59E0B", "#D97706"),
            GridNodeType.SATELLITE_TERMINAL: ("#D97706", "#B45309"),
            GridNodeType.CELLULAR_GATEWAY: ("#EA580C", "#C2410C"),
            # Special nodes - Gray/Red tones
            GridNodeType.HISTORIAN: ("#6B7280", "#4B5563"),
            GridNodeType.HMI: ("#EF4444", "#DC2626"),
        }
        
        ICONS = {
            GridNodeType.CONTROL_CENTER: "⚡",
            GridNodeType.BACKUP_CONTROL_CENTER: "⚡B",
            GridNodeType.SUBSTATION: "⬡",
            GridNodeType.RTU: "R",
            GridNodeType.IED: "I",
            GridNodeType.DATA_CONCENTRATOR: "DC",
            GridNodeType.RELAY: "⚡",
            GridNodeType.METER: "M",
            GridNodeType.GATEWAY: "G",
            GridNodeType.COMM_ROUTER: "◈",
            GridNodeType.COMM_SWITCH: "⬢",
            GridNodeType.COMM_TOWER: "📡",
            GridNodeType.SATELLITE_TERMINAL: "🛰",
            GridNodeType.CELLULAR_GATEWAY: "📶",
            GridNodeType.HISTORIAN: "H",
            GridNodeType.HMI: "🖥",
        }
        
        fill_color, stroke_color = COLORS.get(grid_type, ("#4A90D9", "#2563EB"))
        icon_text = ICONS.get(grid_type, "?")
        
        # Determine shape type based on node category
        if grid_type == GridNodeType.SUBSTATION:
            # Hexagon for substation
            primitive = ShapePrimitive.create_hexagon()
            base_size = (60.0, 60.0)
            connectors = [
                ShapeConnector(edge_position=0.0, label="N"),
                ShapeConnector(edge_position=0.167, label="NE"),
                ShapeConnector(edge_position=0.333, label="SE"),
                ShapeConnector(edge_position=0.5, label="S"),
                ShapeConnector(edge_position=0.667, label="SW"),
                ShapeConnector(edge_position=0.833, label="NW"),
            ]
        elif grid_type in (GridNodeType.CONTROL_CENTER, GridNodeType.BACKUP_CONTROL_CENTER):
            # Rounded rectangle for control centers
            primitive = ShapePrimitive.create_rectangle(corner_radius=0.2)
            base_size = (70.0, 50.0)
            connectors = [
                ShapeConnector(edge_position=0.125, label="N"),
                ShapeConnector(edge_position=0.375, label="E"),
                ShapeConnector(edge_position=0.625, label="S"),
                ShapeConnector(edge_position=0.875, label="W"),
            ]
        elif grid_type in (GridNodeType.COMM_SWITCH, GridNodeType.COMM_ROUTER):
            # Diamond shape for network equipment
            diamond_points = [
                (0.5, 0.0),   # Top
                (1.0, 0.5),   # Right
                (0.5, 1.0),   # Bottom
                (0.0, 0.5),   # Left
            ]
            primitive = ShapePrimitive.create_polygon(diamond_points)
            base_size = (50.0, 50.0)
            connectors = [
                ShapeConnector(edge_position=0.0, label="N"),
                ShapeConnector(edge_position=0.25, label="E"),
                ShapeConnector(edge_position=0.5, label="S"),
                ShapeConnector(edge_position=0.75, label="W"),
            ]
        elif grid_type == GridNodeType.COMM_TOWER:
            # Triangle for tower
            triangle_points = [
                (0.5, 0.0),   # Top
                (1.0, 1.0),   # Bottom right
                (0.0, 1.0),   # Bottom left
            ]
            primitive = ShapePrimitive.create_polygon(triangle_points)
            base_size = (50.0, 55.0)
            connectors = [
                ShapeConnector(edge_position=0.0, label="Top"),
                ShapeConnector(edge_position=0.5, label="R"),
                ShapeConnector(edge_position=0.833, label="L"),
            ]
        elif grid_type in (GridNodeType.HMI, GridNodeType.HISTORIAN):
            # Rectangle for servers/displays
            primitive = ShapePrimitive.create_rectangle(corner_radius=0.1)
            base_size = (55.0, 45.0)
            connectors = [
                ShapeConnector(edge_position=0.125, label="1"),
                ShapeConnector(edge_position=0.375, label="2"),
                ShapeConnector(edge_position=0.625, label="3"),
                ShapeConnector(edge_position=0.875, label="4"),
            ]
        else:
            # Default ellipse for other types
            # Coordinate system: 0% = right (3 o'clock), increases clockwise
            primitive = ShapePrimitive.create_ellipse()
            base_size = (50.0, 50.0)
            connectors = [
                ShapeConnector(edge_position=0.0, label="E"),    # Right
                ShapeConnector(edge_position=0.25, label="S"),   # Bottom
                ShapeConnector(edge_position=0.5, label="W"),    # Left
                ShapeConnector(edge_position=0.75, label="N"),   # Top
            ]
        
        style = ShapeStyle(
            fill_color=fill_color,
            stroke_color=stroke_color,
            stroke_width=2.0,
            icon_text=icon_text,
            icon_font_size=14 if len(icon_text) > 1 else 16,
            icon_color="#FFFFFF",
            icon_bold=True,
        )
        
        shape = ShapeDefinition(
            id=grid_type.name,
            name=grid_type.name.replace("_", " ").title(),
            primitives=[primitive],
            connectors=connectors,
            style=style,
            base_width=base_size[0],
            base_height=base_size[1],
            is_default=True,
            modified=False,
        )
        
        # Calculate and store the path start offset
        shape.path_start_offset = self.calculate_path_start_offset(shape)
        
        return shape


# Convenience function
def get_shape_manager() -> ShapeManager:
    """Get the global ShapeManager instance."""
    return ShapeManager.instance()
