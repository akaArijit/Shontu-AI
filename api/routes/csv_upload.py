"""
CSV Upload Endpoints for Scheme Master Data
Allows MFDs to upload scheme master CSV files for deduplication and benchmark mapping
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import StreamingResponse
import csv
import io
from typing import List, Optional
from datetime import date
from pydantic import BaseModel, validator
from enum import Enum

router = APIRouter(prefix="/mfd/csv", tags=["MFD CSV Upload"])


class SchemeCategory(str, Enum):
    LARGE_CAP = "Large Cap"
    LARGE_AND_MID_CAP = "Large & Mid Cap"
    FLEXI_CAP = "Flexi Cap"
    MULTI_CAP = "Multi Cap"
    MID_CAP = "Mid Cap"
    SMALL_CAP = "Small Cap"
    ELSS = "ELSS"
    SECTORAL_CONSUMPTION = "Sectoral - Consumption"
    SECTORAL_INFRASTRUCTURE = "Sectoral - Infrastructure"
    SECTORAL_PHARMA = "Sectoral - Pharma"
    SECTORAL_BANKING = "Sectoral - Banking"
    SECTORAL_IT = "Sectoral - IT"
    THEMATIC = "Thematic"
    HYBRID_AGGRESSIVE = "Hybrid Aggressive"
    HYBRID_CONSERVATIVE = "Hybrid Conservative"
    DEBT_ULTRA_SHORT = "Debt - Ultra Short Duration"
    DEBT_SHORT = "Debt - Short Duration"
    DEBT_MEDIUM = "Debt - Medium Duration"
    INTERNATIONAL_US = "International - US"
    INTERNATIONAL_GLOBAL = "International - Global"


class SchemeCSVRow(BaseModel):
    """Expected CSV columns for scheme master upload"""
    scheme_code: str
    scheme_name: str
    amc: str
    category: str
    sub_category: Optional[str] = None
    benchmark_index: Optional[str] = None
    fund_manager: Optional[str] = None
    expense_ratio: Optional[float] = None
    aum: Optional[float] = None
    inception_date: Optional[date] = None
    is_active: bool = True
    short_name: Optional[str] = None  # Short name for display

    @validator('category')
    def validate_category(cls, v):
        valid_categories = [c.value for c in SchemeCategory]
        if v not in valid_categories:
            raise ValueError(f"Invalid category. Must be one of: {', '.join(valid_categories)}")
        return v


class CSVUploadResponse(BaseModel):
    success: bool
    message: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    errors: List[dict] = []
    preview: List[dict] = []


class SchemeMasterExport(BaseModel):
    scheme_code: str
    scheme_name: str
    amc: str
    category: str
    sub_category: Optional[str]
    benchmark_index: Optional[str]
    fund_manager: Optional[str]
    expense_ratio: Optional[float]
    aum: Optional[float]
    inception_date: Optional[date]
    is_active: bool
    short_name: Optional[str]


# Expected CSV template
CSV_TEMPLATE_HEADERS = [
    "scheme_code", "scheme_name", "amc", "category", "sub_category",
    "benchmark_index", "fund_manager", "expense_ratio", "aum",
    "inception_date", "is_active", "short_name"
]

CSV_TEMPLATE_EXAMPLE = [
    "INF204K01VX3", "HDFC Top 100 Fund", "HDFC Mutual Fund", "Large Cap", "",
    "NIFTY100_TRI", "Prashant Jain", "1.05", "25000", "2010-01-01", "true", "HDFC Top 100"
]


@router.get("/template")
async def download_csv_template():
    """Download CSV template for scheme master upload"""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_TEMPLATE_HEADERS)
    writer.writerow(CSV_TEMPLATE_EXAMPLE)
    writer.writerow(["INF767K01EW8", "Parag Parikh Flexi Cap Fund", "PPFAS Mutual Fund", "Flexi Cap", "",
                     "NIFTY500_TRI", "Rajeev Thakkar", "0.95", "18000", "2013-05-01", "true", "PPFCF"])
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=scheme_master_template.csv"}
    )


@router.post("/upload/scheme-master", response_model=CSVUploadResponse)
async def upload_scheme_master_csv(
    file: UploadFile = File(...),
    dry_run: bool = Query(False, description="Validate only, don't persist"),
    overwrite: bool = Query(False, description="Overwrite existing schemes")
):
    """
    Upload scheme master CSV file.
    
    Expected columns: scheme_code, scheme_name, amc, category, sub_category,
    benchmark_index, fund_manager, expense_ratio, aum, inception_date, is_active, short_name
    
    Returns validation results and preview of parsed data.
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    content = await file.read()
    try:
        content_str = content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            content_str = content.decode('utf-8-sig')  # Handle BOM
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="Unable to decode CSV. Ensure UTF-8 encoding.")
    
    # Parse CSV
    reader = csv.DictReader(io.StringIO(content_str))
    rows = list(reader)
    
    # Validate each row
    valid_rows = []
    errors = []
    valid_count = 0
    invalid_count = 0
    
    for idx, row in enumerate(rows, start=1):
        try:
            # Clean empty strings
            cleaned = {k: v.strip() if isinstance(v, str) else v for k, v in row.items()}
            
            # Convert empty strings to None for optional fields
            for key in ['sub_category', 'benchmark_index', 'fund_manager', 'short_name']:
                if cleaned.get(key) == '':
                    cleaned[key] = None
            
            # Convert numeric fields
            for key in ['expense_ratio', 'aum']:
                if cleaned.get(key) not in (None, ''):
                    try:
                        cleaned[key] = float(cleaned[key])
                    except ValueError:
                        cleaned[key] = None
            
            # Convert date
            if cleaned.get('inception_date') not in (None, ''):
                try:
                    cleaned['inception_date'] = date.fromisoformat(cleaned['inception_date'])
                except ValueError:
                    try:
                        # Try DD-MM-YYYY format
                        cleaned['inception_date'] = date.strptime(cleaned['inception_date'], '%d-%m-%Y')
                    except ValueError:
                        cleaned['inception_date'] = None
            
            # Convert boolean
            if cleaned.get('is_active') not in (None, ''):
                cleaned['is_active'] = str(cleaned['is_active']).lower() in ('true', '1', 'yes', 'y')
            
            # Validate with Pydantic
            scheme = SchemeCSVRow(**cleaned)
            valid_rows.append(scheme.dict())
            valid_count += 1
            
        except Exception as e:
            errors.append({
                "row": idx,
                "error": str(e),
                "data": row
            })
            invalid_count += 1
    
    # Generate preview (first 10 valid rows)
    preview = valid_rows[:10]
    
    # If not dry run, persist to database
    if not dry_run and valid_count > 0:
        # TODO: Implement database persistence
        # This would use the SchemeDeduplicator to register schemes
        pass
    
    return CSVUploadResponse(
        success=invalid_count == 0,
        message=f"Processed {len(rows)} rows: {valid_count} valid, {invalid_count} invalid",
        total_rows=len(rows),
        valid_rows=valid_count,
        invalid_rows=invalid_count,
        errors=errors,
        preview=preview
    )


@router.get("/download/scheme-master")
async def download_scheme_master():
    """Download current scheme master as CSV"""
    # TODO: Fetch from database
    # For now, return template with example data
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(CSV_TEMPLATE_HEADERS)
    writer.writerow(CSV_TEMPLATE_EXAMPLE)
    
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=scheme_master_export.csv"}
    )


@router.post("/upload/benchmark-mappings")
async def upload_benchmark_mappings_csv(
    file: UploadFile = File(...),
    dry_run: bool = Query(False)
):
    """
    Upload explicit benchmark mappings CSV.
    Expected columns: scheme_code, benchmark_code
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV")
    
    content = await file.read()
    content_str = content.decode('utf-8')
    
    reader = csv.DictReader(io.StringIO(content_str))
    rows = list(reader)
    
    valid = []
    errors = []
    
    for idx, row in enumerate(rows, start=1):
        try:
            scheme_code = row.get('scheme_code', '').strip()
            benchmark_code = row.get('benchmark_code', '').strip()
            
            if not scheme_code or not benchmark_code:
                errors.append({"row": idx, "error": "Missing scheme_code or benchmark_code", "data": row})
                continue
            
            valid.append({"scheme_code": scheme_code, "benchmark_code": benchmark_code})
        except Exception as e:
            errors.append({"row": idx, "error": str(e), "data": row})
    
    return {
        "success": len(errors) == 0,
        "message": f"Processed {len(rows)} rows: {len(valid)} valid, {len(errors)} invalid",
        "total_rows": len(rows),
        "valid_rows": len(valid),
        "invalid_rows": len(errors),
        "errors": errors,
        "mappings": valid if not dry_run else valid[:10]
    }


# Include in main API
def get_csv_router():
    return router