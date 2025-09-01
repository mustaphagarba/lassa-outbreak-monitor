import requests
import numpy as np
import geopandas as gpd
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import json
import hashlib
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
import zipfile
from io import BytesIO
import fiona
from shapely.geometry import Point, Polygon

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class BoundaryInfo:
    name: str
    level: str  
    source: str
    download_date: str
    record_count: int
    geometry_type: str
    crs: str
    file_path: str

class NigerianBoundaryManager:
    pass