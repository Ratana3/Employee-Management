import io
import csv
import logging
import bcrypt
import re
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from flask import request, jsonify
from routes.Auth.config import get_db_connection


class ImportResult:
    """Data class to hold import results"""
    def __init__(self):
        self.imported_count = 0
        self.skipped_count = 0
        self.errors = []
    
    def add_error(self, line_number: int, message: str):
        self.errors.append(f"Line {line_number}: {message}")
        self.skipped_count += 1
    
    def increment_imported(self):
        self.imported_count += 1
    
    def to_response(self, entity_name: str):
        msg = f"Imported {self.imported_count} {entity_name} record(s)."
        if self.skipped_count > 0:
            msg += f" Skipped {self.skipped_count} row(s)."
        
        return {
            "message": msg,
            "imported_count": self.imported_count,
            "skipped_count": self.skipped_count,
            "errors": self.errors
        }

# add more validate functions if needed
class ValidationUtils:
    """Utility class for common validations"""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Validate email format"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    @staticmethod
    def validate_date(date_string: str, format_string: str = '%Y-%m-%d') -> Optional[datetime]:
        """Validate and parse date string"""
        try:
            return datetime.strptime(date_string, format_string)
        except ValueError:
            return None
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Validate phone number format"""
        pattern = r'^\+?1?\d{9,15}$'
        return re.match(pattern, phone.replace(' ', '').replace('-', '')) is not None
    
    @staticmethod
    def sanitize_string(value: str, max_length: int = None) -> str:
        """Sanitize string input"""
        sanitized = value.strip()
        if max_length and len(sanitized) > max_length:
            sanitized = sanitized[:max_length]
        return sanitized

class BaseImportService:
    """Base service class for handling CSV imports"""
    
    def __init__(self, table_name: str, expected_columns: int, unique_field: str):
        self.table_name = table_name
        self.expected_columns = expected_columns
        self.unique_field = unique_field
        self.result = ImportResult()
    
    def validate_file(self, file) -> Tuple[bool, str]:
        """Validate uploaded file"""
        if not file or file.filename == '':
            return False, "No file uploaded or selected"
        return True, ""
    
    def setup_csv_reader(self, file):
        """Setup CSV reader and skip header"""
        try:
            stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
            csv_reader = csv.reader(stream)
            
            try:
                header = next(csv_reader)  # Skip header row
                return csv_reader, ""
            except StopIteration:
                return None, "CSV file is empty"
        except Exception as e:
            return None, f"Error reading CSV file: {str(e)}"
    
    def validate_row(self, row: List[str], line_number: int) -> bool:
        """Validate row column count"""
        if len(row) != self.expected_columns:
            self.result.add_error(
                line_number, 
                f"Wrong number of columns (expected {self.expected_columns}, got {len(row)}). Skipped."
            )
            return False
        return True
    
    def check_duplicate(self, cursor, unique_value: str, line_number: int) -> bool:
        """Check for duplicate records"""
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {self.table_name} WHERE {self.unique_field} = %s", (unique_value,))
            if cursor.fetchone()[0] > 0:
                self.result.add_error(line_number, f"Duplicate {self.unique_field} '{unique_value}'. Skipped.")
                return True
            return False
        except Exception as e:
            self.result.add_error(line_number, f"Error checking duplicate: {str(e)}. Skipped.")
            return True
    
    def process_data(self, row: List[str], line_number: int) -> Optional[Dict[str, Any]]:
        """
        Process row data - override in subclasses for custom processing
        Returns processed data dict or None if processing failed
        """
        # Default implementation - just clean whitespace
        return {f"field_{i}": item.strip() for i, item in enumerate(row)}
    
    def insert_record(self, cursor, processed_data: Dict[str, Any], line_number: int) -> bool:
        """
        Insert record into database - override in subclasses
        Returns True if successful, False otherwise
        """
        raise NotImplementedError("Subclasses must implement insert_record method")
    
    def import_csv(self, file) -> Tuple[Dict[str, Any], int]:
        """Main import method"""
        try:
            # Validate file
            is_valid, error_msg = self.validate_file(file)
            if not is_valid:
                return {"error": error_msg}, 400
            
            # Setup database connection
            logging.debug("Starting database connection.")
            conn = get_db_connection()
            cursor = conn.cursor()
            
            # Setup CSV reader
            csv_reader, error_msg = self.setup_csv_reader(file)
            if not csv_reader:
                return {"error": error_msg}, 400
            
            # Process each row
            for line_number, row in enumerate(csv_reader, start=2):
                # Validate row structure
                if not self.validate_row(row, line_number):
                    continue
                
                # Process data
                processed_data = self.process_data(row, line_number)
                if not processed_data:
                    continue
                
                # Check for duplicates
                unique_value = processed_data.get(self.unique_field)
                if unique_value and self.check_duplicate(cursor, unique_value, line_number):
                    continue
                
                # Insert record
                if self.insert_record(cursor, processed_data, line_number):
                    self.result.increment_imported()
            
            # Commit transaction
            conn.commit()
            cursor.close()
            conn.close()
            logging.debug("Import completed successfully.")
            
            return self.result.to_response(self.table_name), 200
            
        except Exception as e:
            logging.exception(f"Error importing {self.table_name}")
            return {"error": f"Failed to import {self.table_name}", "details": str(e)}, 500

# ====================== Guide on how to add more import services ======================

# 1. Look at the class "EmployeeImportService" below as the main example, it will provide every step of what you have to change when you create new class for other tables
# 2. After done creating a new class for a new table then go to class "ImportFactory" and follow the guide that is provided in there next

class EmployeeImportService(BaseImportService):
    """Service for importing employees"""
    
    def __init__(self):
        super().__init__(
            table_name="employees", # change the table name to your desired table
            expected_columns=5, # change the column numbers depend on what columns you want to insert
            unique_field="email" # if you have a single column that doesn't allow duplicate values , add it in the "unique_field" variable
            # if you have multiple columns that don't allow duplicate values , change the "unique_field" variable to this form :
            # unique_field=["email", "field1", "field2"] 
        )
    
    def process_data(self, row: List[str], line_number: int) -> Optional[Dict[str, Any]]:
        """Process employee data with password hashing"""
        try:
            # add the name of the amount of fields you set like below
            first_name, email, position, department, password = [item.strip() for item in row]
            
            # ============== validate section ============== (Skippable, only important if you need to verify datas before inserting)

            # then add validate statement in here depends on your column , in this case it validates email which makes sure that email is in this form "username@gmail.com"
            # Validate email format
            if not ValidationUtils.validate_email(email):
                self.result.add_error(line_number, f"Invalid email format '{email}'. Skipped.")
                return None
            
            # Hash password
            hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

            # ============== validate section =============== 
            
            # then add those fields inside the return statement
            return {
                'first_name': first_name,
                'email': email,
                'position': position,
                'department': department,
                'password': hashed_password
            }
            
        except Exception as e:
            self.result.add_error(line_number, f"Data processing error: {str(e)}. Skipped.")
            return None
    
    def insert_record(self, cursor, processed_data: Dict[str, Any], line_number: int) -> bool:
        """Insert employee record"""
        try:
            # change the query that depend on your table's name and its columns by following the pattern below. After this, go the class called "ImportFactory"
            cursor.execute(
                "INSERT INTO employees (first_name, email, position, department, password) VALUES (%s, %s, %s, %s, %s)",
                (
                    processed_data['first_name'],
                    processed_data['email'],
                    processed_data['position'],
                    processed_data['department'],
                    processed_data['password']
                )
            )
            return True
        except Exception as e:
            self.result.add_error(line_number, f"Database error: {str(e)}. Skipped.")
            return False

# Import Factory and Handler

class ImportFactory:
    """Enhanced factory with permission mapping"""
    
    # add the table name and its class like the pattern below
    _services = {
        'employees': EmployeeImportService,
        # Add more services as needed
    }
    
    # Map entity types to their required permissions. 
    _permissions = {
        'employees': ['import_employees'], # Specific permission "import_employees"
        # Add more permissions as needed
    }
    
    # After this , navigate to "Main Project/Auth/token.py" and add the specific permission inside the IMPORT_DATA_ENDPOINTS endpoint for permission control (Optional)
    # then just add the action for the "Importdata" page inside the "Access control" page in frontend
    # then go to frontend and find the "Script for importing" and follow the pattern in there for adding new import forms and you're good to go !
    # for .csv file sample , search inside the Documentation/Documents.txt at the section "HOW TO RUN THE PROJECT" and look for this part "📃 Testing resources"

    @classmethod
    def create_service(cls, entity_type: str):
        """Create import service for given entity type"""
        service_class = cls._services.get(entity_type)
        if not service_class:
            raise ValueError(f"Unknown entity type: {entity_type}")
        return service_class()
    
    @classmethod
    def get_required_permissions(cls, entity_type: str):
        """Get required permissions for entity type"""
        return cls._permissions.get(entity_type, [])
    
    @classmethod
    def is_supported(cls, entity_type: str):
        """Check if entity type is supported"""
        return entity_type in cls._services

def handle_import(entity_type: str, file) -> Tuple[Dict[str, Any], int]:
    """Generic import handler function"""
    try:
        service = ImportFactory.create_service(entity_type)
        result, status_code = service.import_csv(file)
        return result, status_code
    except ValueError as e:
        return {"error": str(e)}, 400
    except Exception as e:
        logging.exception(f"Import handler error for {entity_type}")
        return {"error": "Import failed", "details": str(e)}, 500
