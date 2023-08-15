from fastapi import FastAPI, HTTPException, Body, Depends
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pymysql
import os
from datetime import datetime
from dotenv import load_dotenv
from typing import List

app = FastAPI()

# CORSを回避するために追加
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,   # 追記により追加
    allow_methods=["*"],      # 追記により追加
    allow_headers=["*"]       # 追記により追加
)

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


class Item(BaseModel):
    PRD_ID: int
    PRD_CD: str
    PRD_NAME: str
    PRD_PRICE: int


class Purchase(BaseModel):
    EMP_CD: str = "9999999999"
    STORE_CD: str
    POS_NO: str
    items: List[Item]


def get_db_connection():
    connection = pymysql.connect(host=MYSQL_SERVER,
                                 user=MYSQL_USER,
                                 password=MYSQL_PASSWORD,
                                 db=MYSQL_DB)
    return connection


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.post("/search_product/")
def search_product(product_query: ProductQuery = Body(...)):
    code = str(product_query.code)
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            sql = "SELECT PRD_ID, PRD_CD, PRD_NAME, PRD_PRICE FROM M_PRODUCT WHERE PRD_CD = %s"
            cursor.execute(sql, (code,))
            result = cursor.fetchone()
            if result:
                return {
                    "status": "success",
                    "message": {
                        "PRD_ID": result[0],
                        "PRD_CD": result[1],
                        "PRD_NAME": result[2],
                        "PRD_PRICE": result[3]
                    }
                }
            else:
                raise HTTPException(
                    status_code=404, detail="Product not found")
    except Exception as e:
        return {
            "status": "failed",
            "detail": f"An error occurred: {str(e)}"
        }
    finally:
        if connection:
            connection.close()


@app.post("/purchase/")
def purchase(data: Purchase, connection=Depends(get_db_connection)):
    # DB接続
    try:
        with connection.cursor() as cursor:
            # t_txn への登録
            sql_txn = """
            INSERT INTO T_TXN (DATETIME, EMP_CD, STORE_CD, POS_NO, TOTAL_AMT, TTL_AMT_EX_TAX)
            VALUES (NOW(), %s, %s, %s, 0, 0);
            """
            cursor.execute(sql_txn, (data.EMP_CD, data.STORE_CD, data.POS_NO))
            TXN_ID = cursor.lastrowid  # 最後に挿入された行のIDを取得

            # t_txn_dtl への登録
            total_amt_ex_tax = 0
            total_amt = 0
            for i, item in enumerate(data.items, 1):
                sql_dtl = """
                INSERT INTO T_TXN_DTL (TXN_ID, TXN_DTL_ID, PRD_ID, PRD_CD, PRD_NAME, PRD_PRICE, TAX_ID)
                VALUES (%s, %s, %s, %s, %s, %s, '10');
                """
                cursor.execute(sql_dtl, (TXN_ID, i, int(item.PRD_ID),
                               str(item.PRD_CD), str(item.PRD_NAME), int(item.PRD_PRICE)))
                total_amt_ex_tax += item.PRD_PRICE

                # 税率の取得と税込み合計額の計算
                sql_tax = "SELECT PERCENT FROM M_TAX WHERE TAX_CD = '10';"
                cursor.execute(sql_tax)
                tax_percent = cursor.fetchone()[0]
                total_amt += item.PRD_PRICE * (1 + tax_percent)

            # t_txn の TOTAL_AMT と TOTAL_AMT_EX_TAX を更新
            total_amt = int(total_amt)
            total_amt_ex_tax = int(total_amt_ex_tax)
            sql_update = """
            UPDATE t_txn SET TOTAL_AMT = %s, TTL_AMT_EX_TAX = %s WHERE TXN_ID = %s;
            """
            cursor.execute(sql_update, (total_amt, total_amt_ex_tax, TXN_ID))

            connection.commit()

            return {
                "status": "success",
                "message": {
                    "合計金額": total_amt,
                    "合計金額（税抜）": total_amt_ex_tax
                }
            }
    except Exception as e:
        connection.rollback()
        return {
            "status": "failed",
            "detail": f"An error occurred: {str(e)}"
        }
    finally:
        connection.close()
