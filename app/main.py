from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
import pymysql
import os
from dotenv import load_dotenv

app = FastAPI()

# .envファイルを読み込む
load_dotenv()

# 環境変数からデータベース情報を取得
MYSQL_SERVER = os.getenv("MYSQL_SERVER")
MYSQL_USER = os.getenv("MYSQL_USER")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
MYSQL_DB = os.getenv("MYSQL_DB")

# JSONのボディ構造を示すPydanticモデル


class ProductQuery(BaseModel):
    code: str


def get_db_connection():
    connection = pymysql.connect(host=MYSQL_SERVER,
                                 user=MYSQL_USER,
                                 password=MYSQL_PASSWORD,
                                 db=MYSQL_DB)
    return connection


@app.get("/")
def read_root():
    return {"Hello": "World"}

# エンドポイントを変更


@app.post("/search_product/")
def search_product(product_query: ProductQuery = Body(...)):
    code = str(product_query.code)
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = "SELECT PRD_CD, PRD_NAME, PRD_PRICE FROM M_PRODUCT WHERE PRD_CD = %s"
            cursor.execute(sql, (code,))
            result = cursor.fetchone()
            if result:
                return {
                    "PRD_CD": result[0],
                    "PRD_NAME": result[1],
                    "PRD_PRICE": result[2]
                }
            else:
                raise HTTPException(
                    status_code=404, detail="Product not found")
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"An error occurred: {str(e)}")
    finally:
        if connection:
            connection.close()
