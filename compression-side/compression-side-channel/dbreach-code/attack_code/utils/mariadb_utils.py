import mariadb
import random
import string
import subprocess
import os
import time

tablespaces_path = "/var/lib/mysql/"

class MariaDBController:
    def __init__(self, db: str, host: str = "127.0.0.1", port: int = 3307, root_password: str = "your_root_password", container_name: str = "mariadb_container"):
        self.db_name = db
        self.host = host
        self.port = port
        self.db_path = tablespaces_path + db + "/" # db 주소
        self.root_password = root_password
        self.container_name = container_name
        self.old_edit_time = None
        try:
            self.conn = mariadb.connect(
                user="root",
                password=self.root_password,
                host=self.host,
                port=self.port,
                database=self.db_name
            )
            self.cur = self.conn.cursor()
        except mariadb.Error as e:
            print(f"Error connecting to MariaDB: {e}")
            self.conn = None
            self.cur = None
        self.backupdict = dict()

    def get_ibd_mtime(self, container_name, table_path):
        cmd = f"docker exec {container_name} stat -c %Y {table_path}"
        output = subprocess.check_output(cmd, shell=True).decode().strip()
        return int(output)  # UNIX timestamp 반환

    def __flush_and_wait_for_change(self, tablename):
        self.flush_table(tablename)
        max_sleeps = 20
        sleeps = 0
        time.sleep(0.5)
        path = self.db_path+tablename+".ibd"
        # while self.get_ibd_mtime(self.container_name, path) == self.old_edit_time: # .ibd는 mysql 데이터베이스 파일 확장자 명
        #     time.sleep(0.1)
        #     sleeps += 1
        #     if sleeps > max_sleeps:
        #         print("max sleeps")
        #         time.sleep(10)
        #         break
        # if sleeps > 0:
        #     print("done sleeping")
        self.old_edit_time = self.get_ibd_mtime(self.container_name, path)
        self.cur.execute("unlock tables")

    # 테이블 최적화 함수
    def optimize_table(self, tablename : str):
        self.cur.execute("optimize table " + tablename)
        status = False
        result = []
        for line in self.cur:
            result.append(line)
            if line[2] == 'status':
                status = line[3] == 'OK'
        if not status: 
            print("OPTIMIZE TABLE FAILED!")
            for line in result:
                print(line)
        return status
    
    # 각종 sql 문을 데이터베이스에 적용하는 함수
    def flush_table(self, tablename : str):
        self.cur.execute("flush tables " + tablename + " with read lock")


    def drop_table(self, tablename):
        if self.cur:
            try:
                self.cur.execute(f"DROP TABLE IF EXISTS {tablename}")
                self.conn.commit()
            except mariadb.Error as e:
                print(f"Error dropping table {tablename}: {e}")

    def create_basic_table(self, tablename, varchar_len=100, compressed=False, encrypted=False):
        compressed_str = "1" if compressed else "0"
        encrypted_str = "YES" if encrypted else "NO"
        path = self.db_path+tablename+".ibd"
        self.cur.execute("create table " + tablename + " (id INT not null, data VARCHAR(" + str(varchar_len) +
                "), primary key(id)) ENGINE=InnoDB PAGE_COMPRESSED=" + compressed_str )
        self.conn.commit()
        time.sleep(2)
        self.old_edit_time = self.get_ibd_mtime(self.container_name, path)

    def get_table_size(self, tablename, verbose=False):
        table_path = self.db_path + tablename + ".ibd"
        cmd = f"docker exec mariadb_container ls -s --block-size=1 {table_path}"
        output = subprocess.check_output(cmd, shell=True).decode()
    
        table_size = int(output.split()[0])
        return table_size

    def insert_row(self, tablename: str, idx: int, data: str):
        if self.cur:
            try:
                self.cur.execute(f"INSERT INTO {tablename} (id, data) VALUES (%s, %s)", (idx, data))
                self.conn.commit()
                self.__flush_and_wait_for_change(tablename)
            except mariadb.Error as e:
                print(f"Error inserting row {idx} into {tablename}: {e}")

    def update_row(self, tablename: str, idx: int, data: str):
        if self.cur:
            try:
                self.cur.execute(f"UPDATE {tablename} SET data=%s WHERE id=%s", (data, idx))
                self.conn.commit()
                self.__flush_and_wait_for_change(tablename)
            except mariadb.Error as e:
                print(f"Error updating row {idx} in {tablename}: {e}")

    def delete_row(self, tablename: str, idx: int):
        if self.cur:
            try:
                self.cur.execute(f"DELETE FROM {tablename} WHERE id={idx}")
                self.conn.commit()
                self.__flush_and_wait_for_change(tablename)
            except mariadb.Error as e:
                print(f"Error deleting row {idx} from {tablename}: {e}")

    def _stop_mariadb(self):
        try:
            subprocess.check_output(["docker", "stop", self.container_name])
            print(f"Docker container {self.container_name} stopped.")
        except subprocess.CalledProcessError as e:
            print(f"Error stopping Docker container {self.container_name}: {e}")

    def _start_mariadb(self):
        try:
            subprocess.check_output(["docker", "start", self.container_name])
            print(f"Docker container {self.container_name} started.")
            time.sleep(5)  # Wait for MariaDB to start
            self.conn = mariadb.connect(
                user="root",
                password=self.root_password,
                host=self.host,
                port=self.port,
                database=self.db_name
            )
            self.cur = self.conn.cursor()
            print(f"Reconnected to MariaDB in container {self.container_name}.")
        except mariadb.Error as e:
            print(f"Error reconnecting to MariaDB: {e}")
        except subprocess.CalledProcessError as e:
            print(f"Error starting Docker container {self.container_name}: {e}")

    # Backup and restore methods can remain the same if needed, but ensure paths are accessible.

def get_filler_str(data_len: int):
    return ''.join(
        random.choices(
            string.ascii_uppercase + string.ascii_lowercase + string.digits + string.punctuation,
            k=data_len
        )
    )

def get_compressible_str(data_len: int, char='a'):
    return char * data_len

def demo_side_channel_compression():
    """
    압축+암호화가 적용된 테이블을 만들고,
    반복적으로 압축 잘 되는 문자열 vs. 랜덤 문자열을 넣으며
    테이블의 크기 변화를 관찰.
    """
    db_name = "flask_db"  # 기존 설정에 맞춤
    tablename = "victimtable"

    # 1) MariaDBController 생성 (호스트 및 포트 설정 포함)
    controller = MariaDBController(
        db=db_name,
        host="127.0.0.1",
        port=3307,
        root_password="your_root_password",  # 실제 MariaDB root 비밀번호로 변경
        container_name="mariadb_container"  # Docker 컨테이너 이름
    )
    
    # 2) 기존 테이블 있으면 삭제
    controller.drop_table(tablename)
    
    # 3) 압축+암호화 테이블 생성 (VARCHAR(500) 예시)
    #    PAGE_COMPRESSED=1, ENCRYPTED=YES
    controller.create_basic_table(tablename, varchar_len=500, compressed=True, encrypted=True)
    
    # 4) 테이블 초기 사이즈 측정
    initial_size = controller.get_table_size(tablename, verbose=True)
    print(f"[INIT] Table={tablename}, size={initial_size} bytes")
    
    # 5) 반복 시나리오: 압축 문자열 vs 랜덤 문자열
    for i in range(1, 11):
        if i % 2 == 0:
            # 압축 잘 되는 문자열 (ex: 2000 'a' characters)
            data_str = get_compressible_str(2000, char='a')
            data_type = 'compressible'
        else:
            # 난잡한 문자열 (ex: 2000 random ASCII chars)
            data_str = get_filler_str(2000)
            data_type = 'random'
        
        # insert_row
        controller.insert_row(tablename, idx=i, data=data_str)

        # 테이블 사이즈 확인
        current_size = controller.get_table_size(tablename, verbose=True)
        print(f"[STEP {i}] Inserted type={data_type}, size={current_size} bytes")
    
    print("[DONE] Check the logs above for table size changes.")

if __name__ == "__main__":
    print("[*] Setting up DB and table...")
    demo_side_channel_compression()
