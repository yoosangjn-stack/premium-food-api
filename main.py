from fastapi import FastAPI, HTTPException

app = FastAPI()

products = [
    {"id": 1, "name": "프리미엄 사과", "price": 10000, "stock_quantity": 5}
]

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/products")
async def get_products():
    return products

@app.get("/products/{product_id}")
async def get_product(product_id: int):
    for product in products:
        if product["id"] == product_id:
            return product
        
    raise HTTPException(status_code=404, detail="상품을 찾을 수 없습니다.")
