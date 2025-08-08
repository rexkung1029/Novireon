# mongo_crud.py
import logging
from pymongo import MongoClient
from pymongo.errors import PyMongoError
from pymongo import ReturnDocument

class MongoCRUD:
    """
    一個用於執行 MongoDB CRUD 操作的類別，並整合了 logging。
    """
    def __init__(self, client: MongoClient, db_name: str, collection_name: str, logger: logging.Logger):
        """
        初始化 MongoDB 操作。

        :param client: 一個 MongoClient 的實例。
        :param db_name: 資料庫名稱。
        :param collection_name: 集合名稱。
        :param logger: 用於日誌記錄的 logger 實例。
        """
        self.client = client
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]
        self.logger = logger
        self.logger.info(f"Handler for collection '{collection_name}' initialized.")

    def get(self, query: dict):
        """根據查詢條件獲取文件。"""
        self.logger.debug(f"Executing find with query: {query}")
        try:
            results = list(self.collection.find(query))
            self.logger.debug(f"Found {len(results)} document(s) for query: {query}")
            return results
        except PyMongoError as e:
            self.logger.error(f"Failed to get data with query {query}: {e}", exc_info=True)
            return []

    def update_many(self, query: dict, new_values: dict):
        """更新文件。"""
        self.logger.debug(f"Executing update_many with query: {query} and values: {new_values}")
        try:
            result = self.collection.update_many(query, {"$set": new_values})
            if result.matched_count > 0:
                self.logger.info(f"Matched {result.matched_count} and modified {result.modified_count} document(s).")
            else:
                self.logger.warning(f"Update query {query} did not match any documents.")
            return result
        except PyMongoError as e:
            self.logger.error(f"Failed to update data with query {query}: {e}", exc_info=True)
            return None
        
    def update_one(self, query: dict[str, any], new_values: dict[str, any], upsert: bool = False):
        """
        更新單一文件。

        :param query: 查詢條件。
        :param new_values: 要設定的新值。
        :param upsert: 如果為 True，當找不到文件時會插入一個新文件。預設為 False。
        """
        self.logger.debug(f"Executing update_one with query: {query}, upsert={upsert}")
        try:
            # 使用 "$set" 來指定要更新的欄位
            result = self.collection.update_one(query, {"$set": new_values}, upsert=upsert)
            
            if result.upserted_id:
                self.logger.info(f"Upserted new document with ID: {result.upserted_id}")
            elif result.matched_count > 0:
                self.logger.info(f"Matched {result.matched_count} and modified {result.modified_count} document(s).")
            else:
                 # 只有在 upsert=False 時，這個警告才有意義
                 if not upsert:
                    self.logger.warning(f"Update query {query} did not match any documents.")
            return result
        except PyMongoError as e:
            self.logger.error(f"Failed to update data with query {query}: {e}", exc_info=True)
            return None
        
    def append(self, query: dict, field: str, value):
        """在文件的陣列欄位中附加一個值。"""
        self.logger.debug(f"Executing push on field '{field}' with query: {query}")
        try:
            result = self.collection.update_one(query, {"$push": {field: value}})
            if result.matched_count > 0:
                self.logger.info(f"Successfully appended value to field '{field}' for a matched document.")
            else:
                self.logger.warning(f"Append query {query} did not match any documents.")
            return result
        except PyMongoError as e:
            self.logger.error(f"Failed to append data for query {query}: {e}", exc_info=True)
            return None

    def pop(self, query: dict, field: str, direction: int = -1):
            """
            從文件的陣列欄位中彈出一個元素，並返回該元素。
            使用 find_one_and_update 實現原子操作。

            Args:
                query (dict): 查詢條件。
                field (str): 要操作的陣列欄位名稱 (例如 "queue")。
                direction (int): -1 表示彈出第一個元素 (FIFO), 1 表示彈出最後一個元素 (LIFO)。
                                音樂佇列通常使用 -1。
            
            Returns:
                dict | None: 被彈出的元素 (如果成功)，否則返回 None。
            """
            self.logger.debug(f"Executing atomic pop on field '{field}' with query: {query}")
            try:
                # 使用 find_one_and_update 進行原子性的 "查詢並更新"
                # return_document=ReturnDocument.BEFORE 會返回文件在被更新「之前」的樣子
                document_before_update = self.collection.find_one_and_update(
                    query,
                    {"$pop": {field: direction}},
                    return_document=ReturnDocument.BEFORE
                )

                # 如果沒有找到匹配的文件，find_one_and_update 會返回 None
                if not document_before_update:
                    self.logger.warning(f"Pop query {query} did not match any documents.")
                    return None

                # 從更新前的完整文件中，提取出我們感興趣的陣列
                array_before_pop = document_before_update.get(field, [])

                # 如果陣列是空的，表示沒有東西可以 pop
                if not array_before_pop:
                    self.logger.warning(f"Field '{field}' was empty for query {query}.")
                    return None
                
                # 根據彈出的方向，返回正確的元素
                # 如果 direction 是 -1 (從頭部彈出)，被彈出的元素就是陣列的第一個
                # 如果 direction 是 1 (從尾部彈出)，被彈出的元素就是陣列的最後一個
                popped_element = array_before_pop[0] if direction == -1 else array_before_pop[-1]
                
                self.logger.info(f"Successfully popped element from field '{field}'.")
                return popped_element

            except PyMongoError as e:
                self.logger.error(f"Failed to pop data for query {query}: {e}", exc_info=True)
                return None