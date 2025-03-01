from flask import Flask, request, jsonify
import os
import pymysql
import pymongo

app = Flask(__name__)

# 환경변수에서 DB 정보 가져오기
db_host = os.environ.get("DB_HOST", "mariadb_container")
db_user = os.environ.get("DB_USER", "flask_user")
db_password = os.environ.get("DB_PASSWORD", "flask_pass")
db_name = os.environ.get("DB_NAME", "flask_db")

mongo_host = os.environ.get("MONGO_HOST", "mongo_container")
mongo_user = os.environ.get("MONGO_USER", "mongo_root")
mongo_pass = os.environ.get("MONGO_PASS", "mongo_root_password")

@app.route('/')
def hello():
    return "Hello, Compression/Encryption Test!"

@app.route('/mysql-test')
def mysql_test():
    conn = pymysql.connect(
        host=db_host,
        user=db_user,
        password=db_password,
        database=db_name,
        charset='utf8mb4'
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()
        return f"MariaDB version: {version}"
    finally:
        conn.close()

@app.route('/mongo-test')
def mongo_test():
    client = pymongo.MongoClient(
        f"mongodb://{mongo_user}:{mongo_pass}@{mongo_host}:27017/"
    )
    db = client.test_db
    collection = db.test_collection
    doc_id = collection.insert_one({"msg": "Hello from MongoDB"}).inserted_id
    return f"MongoDB Inserted ID: {doc_id}"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
