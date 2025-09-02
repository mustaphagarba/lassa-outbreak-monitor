import rasterio
import rasterio.mask
import rasterio.warp
from rasterio.enums import Resampling
import geopandas as gpd
import pandas as pd
import numpy as np
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union
import json
import logging
from datetime import datetime
from dataclasses import dataclass
import zipfile
from io import BytesIO
import rasterstats
from urllib.parse import urljoin
import warnings


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

warnings.filterwarnings('ignore', category=rasterio.errors.NotGeoreferencedWarning)

@dataclass
class PopulationDataInfo:
    country: str
    year: int
    resolution: str  # '1km', '100m', etc.
    data_type: str  # 'total_population', 'age_groups', etc.
    source_url: str
    file_path: str
    download_date: str
    file_size_mb: float

class WorldPopManager:
    def __init__(self, data_dir: str = "data", boundary_manager=None):
        self.data_dir = Path(data_dir)
        self.population_dir = self.data_dir / "population"
        self.population_dir.mkdir(parents=True, exist_ok=True)
        
        self.raw_dir = self.population_dir / "raw"
        self.processed_dir = self.population_dir / "processed"
        self.cache_dir = self.population_dir / "cache"
        
        for dir_path in [self.raw_dir, self.processed_dir, self.cache_dir]:
            dir_path.mkdir(exist_ok=True)
        
        # Store boundary manager reference
        self.boundary_manager = boundary_manager
        
        # WorldPop data sources for Nigeria
        self.worldpop_base_url = "https://data.worldpop.org/GIS/Population/Global_2000_2020_1km_UNadj/"
        self.worldpop_constrained_url = "https://data.worldpop.org/GIS/Population/Global_2000_2020_Constrained/2020/BSGM/"
        
        # Available years and datasets
        self.available_years = list(range(2010, 2021))  # WorldPop coverage
        self.nigeria_iso3 = "NGA"
        
        # Metadata storage
        self.metadata_file = self.population_dir / "population_metadata.json"
        self.metadata = self._load_metadata()