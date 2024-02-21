import requests
import pandas as pd
import re
from .metabase_pandas_api_logger import setup_logging
import os
import time
import io

class MetabaseAPI:
    """
    A class for interacting with Metabase using the requests library.
    """
    
    def __init__(self, metabase_url: str, username: str, password: str):
        """
        Initialize the MetabaseAPI.

        Args:
        - metabase_url (str): The URL of your Metabase instance.
        - username (str): Metabase username.
        - password (str): Metabase password.
        """
        
        self.metabase_url = metabase_url.strip("/")
        self.username = username
        self.password = password
        self.session = self._login()
        self.logger = setup_logging(logger_name="metabase_api")
    
    def _login(self):
        """
        Log in to Metabase and return a session.

        Returns:
        - requests.Session: A session object for making authenticated requests.
        """
        
        session = requests.Session()
        login_url = f"{self.metabase_url}/api/session"
        login_data = {
            "username": self.username,
            "password": self.password
        }
        
        try:
            response = session.post(login_url, json=login_data)
            response.raise_for_status()
            
        except Exception as e:
            self.logger.error(str(e))
            raise RuntimeError(str(e))

        return session
    
    def custom_query(self, sql: str, database_id: int = 6):
        """
        Custom query through metabase API using database id and custom query.

        Args:
            query (str): The SQL query as you wish.
            database_id (int): The ID of the database where the query will be executed (default is 6 or V3 prod).

        Returns:
            json response
        """
        self.logger.info("Querying based on custom query...")
        endpoint = f"{self.metabase_url}/api/dataset"
        retries = 0
        max_retries = 3
        retry_delay = 5
        while retries <= max_retries:
            try:
                merged_dict = None
                len_rows = 2000 # Magic number just to trigger the while loop
                offset = 0
                pattern = re.compile(r'(limit\s*)(\d+)(?![^\(]*\))', re.IGNORECASE)
                # This (limit\s*)(\d+)(?![^\(]*\)) matching the word "limit" followed by a space and a number. Only if this pattern is not inside parentheses, to avoid matching nested queries.
                cleaned_sql = re.sub(pattern, "", sql)
                match = pattern.search(sql)
                limit_value = int(match.group(2)) if match else None
                while len_rows > 0:
                    query = cleaned_sql
                    if limit_value is not None:
                        query += f"\nLIMIT {str(limit_value)} OFFSET {str(offset)}"
                        limit_value -= 2000
                    else:
                        query += f"\nOFFSET {str(offset)}"
                        
                    payload = {
                        "type":"native",
                        "native":{
                            "query":f"{query}",
                            "template-tags":{}
                            },
                        "database":database_id,
                        "parameters":[]
                    }
                    response = self.session.post(endpoint, json=payload)
                    response.raise_for_status()
                    current_batch = response.json()
                    
                    if 'error_type' in current_batch.keys() or 'error' in current_batch.keys():
                        break
                    
                    if merged_dict is not None:
                        merged_dict = MetabaseAPI.deep_merge(merged_dict, current_batch)
                    else:
                        merged_dict = current_batch
                        
                    len_rows = len(current_batch.get('data').get('rows'))
                    offset += 2000
                    
                    if limit_value is not None and limit_value < 0:
                        break
                    
                if 'error_type' in current_batch.keys() or 'error' in current_batch.keys():
                    error_type = current_batch.get('error_type')
                    error_message = current_batch.get('error')
                    if "canceling statement due to conflict with recovery" in error_message:
                        self.logger.warning(f"Recovery-related error encountered. Retrying... (Attempt {retries+1}/{max_retries})")
                        retries += 1
                        time.sleep(retry_delay)
                        continue
                    else:
                        self.logger.error(f"Error during custom query execution.\nError type: {error_type}\nError: {error_message}\nReturn value -> None")
                        break
                else:
                    break
            
            except Exception as e:
                self.logger.error(str(e))
                raise RuntimeError(str(e))
            
        if retries >= max_retries:
            self.logger.error("Maximum retry attempts reached. Aborting query.")
            return None
            
        self.logger.info("Querying completed.")
        self.result = merged_dict
        return self
    
    @staticmethod
    def deep_merge(dict1, dict2):
        """
        Deep merges two dictionaries, combining their keys and values.

        This function performs a deep merge of two dictionaries, combining their keys
        and values in a way that handles nested dictionaries and lists of dictionaries.

        Args:
            dict1 (dict): The first dictionary to merge.
            dict2 (dict): The second dictionary to merge.

        Returns:
            dict: A new dictionary that is the result of merging the input dictionaries.
        """
        logger = setup_logging(logger_name="metabase_api", log_file_path=os.getenv('SYSTEM_LOG_PATH'))
        try:
            merged_dict = {}
            all_keys = set(dict1.keys()) | set(dict2.keys())

            for key in all_keys:
                val1 = dict1.get(key)
                val2 = dict2.get(key)

                if isinstance(val1, list) and isinstance(val2, list):
                    if all(isinstance(item, dict) and 'name' in item for item in val1 + val2):
                        temp_dict = {d['name']: d for d in val1 + val2}
                        merged_dict[key] = list(temp_dict.values())
                    else:
                        merged_dict[key] = val1 + val2
                elif isinstance(val1, dict) and isinstance(val2, dict):
                    merged_dict[key] = MetabaseAPI.deep_merge(val1, val2)
                else:
                    merged_dict[key] = val1 if val1 is not None else val2
                
        except Exception as e:
            logger.error(str(e))
            raise RuntimeError(str(e))

        return merged_dict
    
    def export_card(self, card_number=None, file_path=None, chunk_size=None):
        """
        Export data from a Metabase card and save it in the specified format and path.

        Args:
            self: The Metabase API client.
            card_number (int): The card number to export data from.
            file_path (str, optional): The path to save the exported file.

        Returns:
            None: The function saves the exported data to the specified file path.
        """
        self.logger.info(f"Fetching data from Metabase - Card:{card_number}...")
        retries = 0
        max_retries = 3
        retry_delay = 5

        while retries <= max_retries:
            try:
                if not card_number:
                    raise ValueError("card_number must not be empty")

                endpoint = f"{self.metabase_url}/api/card/{card_number}/query/csv"

                if chunk_size and file_path:
                    with self.session.post(endpoint, stream=True) as r:
                        if r.status_code != 200:
                            raise Exception(f"Failed to stream data: status code {r.status_code}")
                        
                        total_size = int(r.headers.get('content-length', 0))
                        downloaded_size = 0
                        with open(file_path, "wb") as file:
                            for chunk in r.iter_content(chunk_size=chunk_size):
                                file.write(chunk)
                                downloaded_size += len(chunk)
                                if total_size > 0:
                                    percent_complete = (downloaded_size / total_size) * 100
                                    print(f"\rDownloaing: {percent_complete} %", end='')
                                else:
                                    print(f"Downloaded {downloaded_size} bytes.")
                        self.logger.info(f"Card:{card_number} download successfully.")
                elif file_path:
                    csv_response = self.session.post(endpoint)
                    if csv_response.status_code != 200:
                        raise Exception(f"Failed to fetch data: status code {csv_response.status_code}")
                    else:
                        with open(file_path, "wb") as file:
                            file.write(csv_response.content)
                else:
                    csv_response = self.session.post(endpoint)
                    if csv_response.status_code != 200:
                        raise Exception(f"Failed to fetch data: status code {csv_response.status_code}")
                    else:
                        self.result = csv_response.content.decode('utf-8')

                break

            except Exception as e:
                self.logger.error(f"Error fetching data: {e}")
                retries += 1
                if retries <= max_retries:
                    self.logger.info(f"Retrying... Attempt {retries}/{max_retries}")
                    time.sleep(retry_delay)
                else:
                    self.logger.error("Max retries reached. Giving up.")
                    raise

        return self

    
    def to_pandas_dataframe(self, response_data=None):
        """
        Convert the query response to a Pandas DataFrame.

        Args:
            response_data (json_response): The result from any query method in this module.
            If None, uses the instance's result attribute.

        Returns:
            Pandas DataFrame: A DataFrame representation of the query response, or
            an empty DataFrame if the response is invalid or empty.
        """
        try:
            if response_data is None:
                response_data = self.result
                
            if response_data and isinstance(response_data, str):
                return pd.read_csv(io.StringIO(response_data))
        
            if isinstance(response_data, dict) and 'data' in response_data and 'rows' in response_data['data'] and 'cols' in response_data['data']:
                rows_data = response_data['data']['rows']
                columns = [col.get('name') for col in response_data['data']['cols']]
                return pd.DataFrame(rows_data, columns=columns)

            else:
                self.logger.warning("Invalid or empty response data for DataFrame conversion.")
                return pd.DataFrame()

        except Exception as e:
            self.logger.error(str(e))
            raise RuntimeError(str(e))
    
    def to_string(self, response_data=None):
        """
        Convert the query response to a string.

        Args:
            response_data (json_response): The result from any query method in this module.

        Returns:
            String
        """
        try:
            if response_data is None:
                response_data = self.result
                
            if response_data and isinstance(response_data, str):
                self.logger.info("The response data is already in string format.")
                return response_data
            
            if response_data and 'data' in response_data and 'rows' in response_data['data']:
                rows_data = response_data['data']['rows']
                if rows_data and rows_data[0]:
                    return str(rows_data[0][0])
                else:
                    self.logger.warning("Query returned no rows")
                    return None
            else:
                self.logger.warning("Invalid or empty response data.")
                return None
        except Exception as e:
            self.logger.error(str(e))
            raise RuntimeError(str(e))