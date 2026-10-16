"""
A2UI (Agent-to-User Interface) Declarative Protocol Schemas
Flat adjacency-list component model and data-model separation.
"""
from typing import Any, Dict, List, Optional, Literal, Union
from pydantic import BaseModel, Field


class A2UIBoundValue(BaseModel):
    """Represents a value that can be either a literal or an RFC 6901 JSON pointer."""
    literalString: Optional[str] = None
    literalNumber: Optional[float] = None
    literalBoolean: Optional[bool] = None
    path: Optional[str] = None  # e.g., "/loan/amount" or "/eb/units"

    @classmethod
    def from_val(cls, val: Union[str, int, float, bool]) -> "A2UIBoundValue":
        if isinstance(val, bool):
            return cls(literalBoolean=val)
        if isinstance(val, (int, float)):
            return cls(literalNumber=float(val))
        return cls(literalString=str(val))

    @classmethod
    def from_path(cls, path: str) -> "A2UIBoundValue":
        return cls(path=path)


class ChildrenList(BaseModel):
    """Flat list of child component IDs referencing adjacent components."""
    explicitList: List[str] = Field(default_factory=list)


# Component Definitions
class CardComponent(BaseModel):
    title: Optional[str] = None
    subtitle: Optional[str] = None
    children: ChildrenList = Field(default_factory=ChildrenList)
    variant: Literal["default", "elevated", "outlined", "accent"] = "default"


class ColumnComponent(BaseModel):
    children: ChildrenList = Field(default_factory=ChildrenList)
    justify: Literal["start", "center", "end", "between", "around"] = "start"
    align: Literal["start", "center", "end", "stretch"] = "stretch"
    gap: Optional[int] = 3


class RowComponent(BaseModel):
    children: ChildrenList = Field(default_factory=ChildrenList)
    justify: Literal["start", "center", "end", "between", "around"] = "between"
    align: Literal["start", "center", "end", "stretch"] = "center"
    gap: Optional[int] = 3


class SliderComponent(BaseModel):
    label: str
    min: float
    max: float
    step: float = 1.0
    valuePath: str
    unit: Optional[str] = ""
    format: Optional[str] = None  # e.g., "currency", "integer", "decimal", "percent"


class TextFieldComponent(BaseModel):
    label: str
    placeholder: Optional[str] = None
    valuePath: str
    inputType: Literal["text", "number", "email"] = "number"


class ChoiceOption(BaseModel):
    label: str
    value: Union[str, int, float]


class ChoicePickerComponent(BaseModel):
    label: str
    options: List[ChoiceOption]
    valuePath: str


class ButtonComponent(BaseModel):
    text: str
    variant: Literal["primary", "secondary", "outline", "danger"] = "primary"
    actionId: str
    payload: Optional[Dict[str, Any]] = None


class MetricComponent(BaseModel):
    label: str
    valuePath: str
    format: Optional[str] = "currency"  # "currency", "number", "percent", "string"
    subtext: Optional[str] = None
    color: Optional[str] = "blue"  # "blue", "green", "emerald", "indigo", "rose", "amber"


class AlertComponent(BaseModel):
    title: str
    message: str
    severity: Literal["info", "warning", "success", "error"] = "info"


class DividerComponent(BaseModel):
    pass


class A2UIComponentItem(BaseModel):
    """Single item in the flat adjacency list."""
    id: str
    component: Dict[str, Any]


# Surface Messages
class CreateSurfacePayload(BaseModel):
    surfaceId: str
    title: str
    rootComponentId: str


class UpdateComponentsPayload(BaseModel):
    surfaceId: str
    components: List[A2UIComponentItem]


class UpdateDataModelPayload(BaseModel):
    surfaceId: str
    dataModel: Dict[str, Any]
