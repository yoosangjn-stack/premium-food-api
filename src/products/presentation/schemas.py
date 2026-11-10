from pydantic import BaseModel, ConfigDict, Field, model_validator

from products.domain.entities import MAX_INTEGER


class ProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    price: int = Field(ge=0, le=MAX_INTEGER, strict=True)
    stock_quantity: int = Field(default=0, ge=0, le=MAX_INTEGER, strict=True)


class ProductUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    price: int | None = Field(default=None, ge=0, le=MAX_INTEGER, strict=True)
    stock_quantity: int | None = Field(default=None, ge=0, le=MAX_INTEGER, strict=True)

    @model_validator(mode="after")
    def validate_changes(self):
        if not self.model_fields_set or any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Provide at least one field; explicit null is not allowed.")
        return self


class ProductResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    price: int
    stock_quantity: int


class ProductPageResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    size: int
