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
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.boundaries_dir = self.data_dir / "boundaries"
        self.boundaries_dir.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        self.raw_dir = self.boundaries_dir / "raw"
        self.processed_dir = self.boundaries_dir / "processed"
        self.cache_dir = self.boundaries_dir / "cache"
        
        for dir_path in [self.raw_dir, self.processed_dir, self.cache_dir]:
            dir_path.mkdir(exist_ok=True)
        
        # Boundary data sources
        self.data_sources = {
            'gadm': {
                'states': 'https://geodata.ucdavis.edu/gadm/gadm4.1/gpkg/gadm41_NGA.gpkg',
                'description': 'Global Administrative Areas (GADM) v4.1'
            },
            'geoboundaries': {
                'states': 'https://www.geoboundaries.org/api/current/gbOpen/NGA/ADM1/',
                'lgas': 'https://www.geoboundaries.org/api/current/gbOpen/NGA/ADM2/',
                'description': 'GeoBoundaries Open Global Database'
            }
        }
        
        # Nigerian states and FCT reference data for validation
        self.nigerian_states = {
            'abia', 'adamawa', 'akwa ibom', 'anambra', 'bauchi', 'bayelsa',
            'benue', 'borno', 'cross river', 'delta', 'ebonyi', 'edo',
            'ekiti', 'enugu', 'gombe', 'imo', 'jigawa', 'kaduna',
            'kano', 'katsina', 'kebbi', 'kogi', 'kwara', 'lagos',
            'nasarawa', 'niger', 'ogun', 'ondo', 'osun', 'oyo',
            'plateau', 'rivers', 'sokoto', 'taraba', 'yobe', 'zamfara',
            'fct'  # Federal Capital Territory
        }
        
        # Load any existing metadata
        self.metadata_file = self.boundaries_dir / "boundary_metadata.json"
        self.metadata = self._load_metadata()
    
    def _load_metadata(self) -> Dict:
        """Load existing boundary metadata"""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load metadata: {e}")
        return {'datasets': {}, 'last_updated': None}
    
    def _save_metadata(self):
        """Save boundary metadata"""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self.metadata, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Could not save metadata: {e}")
    
    def _get_file_hash(self, file_path: Path) -> str:
        """Generate hash of file for change detection"""
        if not file_path.exists():
            return ""
        
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def _download_file(self, url: str, output_path: Path, force: bool = False) -> bool:
        """Download file with caching and hash checking"""
        if output_path.exists() and not force:
            logger.info(f"File already exists: {output_path.name}")
            return True
        
        try:
            logger.info(f"Downloading from {url}...")
            response = requests.get(url, stream=True, timeout=300)
            response.raise_for_status()
            
            # Write to temporary file first
            temp_path = output_path.with_suffix('.tmp')
            with open(temp_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            # Move to final location
            temp_path.rename(output_path)
            logger.info(f"Downloaded: {output_path.name} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")
            return True
            
        except Exception as e:
            logger.error(f"Download failed: {e}")
            if temp_path.exists():
                temp_path.unlink()
            return False
    
    def _standardize_names(self, gdf: gpd.GeoDataFrame, name_column: str) -> gpd.GeoDataFrame:
        """Standardize Nigerian place names for consistency"""
        gdf_clean = gdf.copy()
        
        # Common name standardizations for Nigerian states
        name_mapping = {
            # Handle FCT variations
            'federal capital territory': 'fct',
            'abuja': 'fct',
            'f.c.t': 'fct',
            # Handle state name variations
            'akwa-ibom': 'akwa ibom',
            'cross-river': 'cross river',
            # Add more mappings as needed
        }
        
        # Clean and standardize names
        gdf_clean[name_column] = gdf_clean[name_column].str.lower().str.strip()
        
        # Apply mappings
        for old_name, new_name in name_mapping.items():
            gdf_clean[name_column] = gdf_clean[name_column].str.replace(old_name, new_name)
        
        return gdf_clean
    
    def download_gadm_boundaries(self, force: bool = False) -> bool:
        """Download GADM boundaries for Nigeria"""
        logger.info("Downloading GADM boundaries...")
        
        url = self.data_sources['gadm']['states']
        output_file = self.raw_dir / "gadm41_NGA.gpkg"
        
        if self._download_file(url, output_file, force):
            # Update metadata
            self.metadata['datasets']['gadm'] = {
                'source': url,
                'downloaded': datetime.now().isoformat(),
                'file_path': str(output_file),
                'file_hash': self._get_file_hash(output_file)
            }
            self._save_metadata()
            return True
        
        return False
    
    def download_geoboundaries(self, force: bool = False) -> Tuple[bool, bool]:
        """Download GeoBoundaries data for states and LGAs"""
        logger.info("Downloading GeoBoundaries data...")
        
        success_states = success_lgas = False
        
        # Download states (ADM1)
        try:
            states_api = self.data_sources['geoboundaries']['states']
            response = requests.get(states_api, timeout=30)
            response.raise_for_status()
            
            states_info = response.json()
            states_url = states_info.get('gjDownloadURL') or states_info.get('zipDownloadURL')
            
            if states_url:
                states_file = self.raw_dir / "nigeria_states_geoboundaries.geojson"
                success_states = self._download_file(states_url, states_file, force)
                
                if success_states:
                    self.metadata['datasets']['geoboundaries_states'] = {
                        'source': states_url,
                        'downloaded': datetime.now().isoformat(),
                        'file_path': str(states_file),
                        'file_hash': self._get_file_hash(states_file)
                    }
        
        except Exception as e:
            logger.error(f"Failed to download states from GeoBoundaries: {e}")
        
        # Download LGAs (ADM2)
        try:
            lgas_api = self.data_sources['geoboundaries']['lgas']
            response = requests.get(lgas_api, timeout=30)
            response.raise_for_status()
            
            lgas_info = response.json()
            lgas_url = lgas_info.get('gjDownloadURL') or lgas_info.get('zipDownloadURL')
            
            if lgas_url:
                lgas_file = self.raw_dir / "nigeria_lgas_geoboundaries.geojson"
                success_lgas = self._download_file(lgas_url, lgas_file, force)
                
                if success_lgas:
                    self.metadata['datasets']['geoboundaries_lgas'] = {
                        'source': lgas_url,
                        'downloaded': datetime.now().isoformat(),
                        'file_path': str(lgas_file),
                        'file_hash': self._get_file_hash(lgas_file)
                    }
        
        except Exception as e:
            logger.error(f"Failed to download LGAs from GeoBoundaries: {e}")
        
        if success_states or success_lgas:
            self._save_metadata()
        
        return success_states, success_lgas
    def _empty_gdf(self, level: str = "state") -> gpd.GeoDataFrame:
        """Return an empty GeoDataFrame with standard columns"""
        if level == "state":
            columns = ['name', 'gid', 'hasc_code', 'geometry', 'level', 'source', 'area_km2']
        else:  # lga
            columns = ['name', 'state_name', 'gid', 'hasc_code', 'geometry', 'level', 'source', 'area_km2']
        
        return gpd.GeoDataFrame(columns=columns, geometry='geometry', crs="EPSG:4326")

    
    def process_gadm_data(self) -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
        """Process GADM data into standardized state and LGA boundaries"""
        gadm_file = self.raw_dir / "gadm41_NGA.gpkg"
        
        if not gadm_file.exists():
            logger.error("GADM file not found. Download first.")
            return self._empty_gdf("state"), self._empty_gdf("lga")
        
        try:
            logger.info("Processing GADM data...")
            
            # List available layers
            layers = fiona.listlayers(str(gadm_file))
            logger.info(f"Available layers: {layers}")
            
            # Default to empty
            states_gdf = self._empty_gdf("state")
            lgas_gdf = self._empty_gdf("lga")
            
            # Process states (ADM_LEVEL 1)
            try:
                states_raw = gpd.read_file(gadm_file, layer='ADM_ADM_1')
                logger.info(f"Loaded {len(states_raw)} states from GADM")
                states_gdf = self._standardize_names(states_raw, 'NAME_1')
                states_gdf = states_gdf.rename(columns={'NAME_1': 'name','GID_1': 'gid','HASC_1': 'hasc_code'})
                states_gdf = states_gdf[['name', 'gid', 'hasc_code', 'geometry']].copy()
                states_gdf['level'] = 'state'
                states_gdf['source'] = 'gadm'
                states_gdf['area_km2'] = states_gdf.geometry.to_crs('EPSG:3857').area / 1e6
            except Exception as e:
                logger.error(f"Error processing GADM states: {e}")
            
            # Process LGAs (ADM_LEVEL 2)
            try:
                lgas_raw = gpd.read_file(gadm_file, layer='ADM_ADM_2')
                logger.info(f"Loaded {len(lgas_raw)} LGAs from GADM")
                lgas_gdf = self._standardize_names(lgas_raw, 'NAME_2')
                lgas_gdf = lgas_gdf.rename(columns={'NAME_1': 'state_name','NAME_2': 'name','GID_2': 'gid','HASC_2': 'hasc_code'})
                lgas_gdf = self._standardize_names(lgas_gdf, 'state_name')
                lgas_gdf = lgas_gdf[['name', 'state_name', 'gid', 'hasc_code', 'geometry']].copy()
                lgas_gdf['level'] = 'lga'
                lgas_gdf['source'] = 'gadm'
                lgas_gdf['area_km2'] = lgas_gdf.geometry.to_crs('EPSG:3857').area / 1e6
            except Exception as e:
                logger.error(f"Error processing GADM LGAs: {e}")
            
            return states_gdf, lgas_gdf
    
        except Exception as e:
            logger.error(f"Error processing GADM data: {e}")
            return self._empty_gdf("state"), self._empty_gdf("lga")

    
    def process_geoboundaries_data(self) -> Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
        """Process GeoBoundaries data"""
        states_file = self.raw_dir / "nigeria_states_geoboundaries.geojson"
        lgas_file = self.raw_dir / "nigeria_lgas_geoboundaries.geojson"
        
        states_gdf = self._empty_gdf("state")
        lgas_gdf = self._empty_gdf("lga")
        
        # Process states
        if states_file.exists():
            try:
                logger.info("Processing GeoBoundaries states...")
                states_raw = gpd.read_file(states_file)
                name_col = 'shapeName' if 'shapeName' in states_raw.columns else 'name'
                states_gdf = self._standardize_names(states_raw, name_col)
                states_gdf = states_gdf.rename(columns={name_col: 'name'})
                states_gdf['level'] = 'state'
                states_gdf['source'] = 'geoboundaries'
                states_gdf['gid'] = states_gdf.index.astype(str)
                states_gdf['area_km2'] = states_gdf.geometry.to_crs('EPSG:3857').area / 1e6
            except Exception as e:
                logger.error(f"Error processing GeoBoundaries states: {e}")
        
        # Process LGAs
        if lgas_file.exists():
            try:
                logger.info("Processing GeoBoundaries LGAs...")
                lgas_raw = gpd.read_file(lgas_file)
                name_col = 'shapeName' if 'shapeName' in lgas_raw.columns else 'name'
                lgas_gdf = self._standardize_names(lgas_raw, name_col)
                lgas_gdf = lgas_gdf.rename(columns={name_col: 'name'})
                lgas_gdf['level'] = 'lga'
                lgas_gdf['source'] = 'geoboundaries'
                lgas_gdf['gid'] = lgas_gdf.index.astype(str)
                lgas_gdf['area_km2'] = lgas_gdf.geometry.to_crs('EPSG:3857').area / 1e6
                if 'shapeGroup' in lgas_raw.columns:
                    lgas_gdf['state_name'] = lgas_raw['shapeGroup'].str.lower().str.strip()
                    lgas_gdf = self._standardize_names(lgas_gdf, 'state_name')
            except Exception as e:
                logger.error(f"Error processing GeoBoundaries LGAs: {e}")
        
        return states_gdf, lgas_gdf

    
    def create_unified_boundaries(self) -> Tuple[Optional[gpd.GeoDataFrame], Optional[gpd.GeoDataFrame]]:
        """Create unified, standardized boundary datasets"""
        logger.info("Creating unified boundary datasets...")
        
        # Get data from all sources
        gadm_states, gadm_lgas = self.process_gadm_data()
        geo_states, geo_lgas = self.process_geoboundaries_data()
        
        # Combine states (prefer GADM, fallback to GeoBoundaries)
        final_states = gadm_states if len(gadm_states) > 0 else geo_states
        if final_states is None or len(final_states) == 0:
            final_states = self._empty_gdf("state")
            logger.warning("No state boundaries available. Creating empty dataset.")
        
        # Combine LGAs (prefer GADM, fallback to GeoBoundaries)
        final_lgas = gadm_lgas if len(gadm_lgas) > 0 else geo_lgas
        if final_lgas is None or len(final_lgas) == 0:
            final_lgas = self._empty_gdf("lga")
            logger.warning("No LGA boundaries available. Creating empty dataset.")
        
        # Save processed boundaries (always writes a file)
        states_output = self.processed_dir / "nigeria_states_unified.geojson"
        final_states.to_file(states_output, driver='GeoJSON')
        logger.info(f"Saved unified states to {states_output}")
        
        lgas_output = self.processed_dir / "nigeria_lgas_unified.geojson"
        final_lgas.to_file(lgas_output, driver='GeoJSON')
        logger.info(f"Saved unified LGAs to {lgas_output}")
        
        # Update metadata
        self.metadata['processed'] = self.metadata.get('processed', {})
        self.metadata['processed']['states'] = {
            'file_path': str(states_output),
            'record_count': len(final_states),
            'processed_date': datetime.now().isoformat(),
            'source': final_states['source'].iloc[0] if len(final_states) > 0 else 'none'
        }
        self.metadata['processed']['lgas'] = {
            'file_path': str(lgas_output),
            'record_count': len(final_lgas),
            'processed_date': datetime.now().isoformat(),
            'source': final_lgas['source'].iloc[0] if len(final_lgas) > 0 else 'none'
        }
        
        self._save_metadata()
        return final_states, final_lgas
    
    def load_boundaries(self, level: str = 'both') -> Union[gpd.GeoDataFrame, Tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]]:
        """Load processed boundary data"""
        states_file = self.processed_dir / "nigeria_states_unified.geojson"
        lgas_file = self.processed_dir / "nigeria_lgas_unified.geojson"
        
        if level == 'states' or level == 'state':
            if not states_file.exists():
                logger.error("Processed states file not found. Run create_unified_boundaries() first.")
                return None
            return gpd.read_file(states_file)
        
        elif level == 'lgas' or level == 'lga':
            if not lgas_file.exists():
                logger.error("Processed LGAs file not found. Run create_unified_boundaries() first.")
                return None
            return gpd.read_file(lgas_file)
        
        else:  # both
            states_gdf = lgas_gdf = None
            
            if states_file.exists():
                states_gdf = gpd.read_file(states_file)
            if lgas_file.exists():
                lgas_gdf = gpd.read_file(lgas_file)
            
            return states_gdf, lgas_gdf
    
    def spatial_join_data(self, df: pd.DataFrame, lat_col: str, lon_col: str, 
                         level: str = 'state') -> pd.DataFrame:
        """Spatial join point data with administrative boundaries"""
        
        # Load appropriate boundaries
        if level == 'state':
            boundaries = self.load_boundaries('states')
        else:
            boundaries = self.load_boundaries('lgas')
        
        if boundaries is None:
            logger.error(f"No {level} boundaries available for spatial join")
            return df
        
        # Create GeoDataFrame from points
        geometry = gpd.points_from_xy(df[lon_col], df[lat_col])
        points_gdf = gpd.GeoDataFrame(df, geometry=geometry, crs='EPSG:4326')
        
        # Ensure same CRS
        boundaries = boundaries.to_crs('EPSG:4326')
        
        # Perform spatial join
        joined = gpd.sjoin(points_gdf, boundaries, how='left', predicate='within')
        
        # Drop geometry column and return as regular DataFrame
        result = pd.DataFrame(joined.drop(columns='geometry'))
        
        logger.info(f"Spatial join completed: {len(result)} records processed")
        return result
    
    def get_boundary_info(self) -> Dict[str, BoundaryInfo]:
        """Get information about available boundary datasets"""
        info = {}
        
        states_gdf, lgas_gdf = self.load_boundaries('both')
        
        if states_gdf is not None:
            info['states'] = BoundaryInfo(
                name="Nigerian States",
                level="state",
                source=states_gdf['source'].iloc[0] if len(states_gdf) > 0 else 'unknown',
                download_date=self.metadata.get('processed', {}).get('states', {}).get('processed_date', 'unknown'),
                record_count=len(states_gdf),
                geometry_type=str(states_gdf.geometry.geom_type.iloc[0]) if len(states_gdf) > 0 else 'unknown',
                crs=str(states_gdf.crs),
                file_path=str(self.processed_dir / "nigeria_states_unified.geojson")
            )
        
        if lgas_gdf is not None:
            info['lgas'] = BoundaryInfo(
                name="Nigerian LGAs",
                level="lga", 
                source=lgas_gdf['source'].iloc[0] if len(lgas_gdf) > 0 else 'unknown',
                download_date=self.metadata.get('processed', {}).get('lgas', {}).get('processed_date', 'unknown'),
                record_count=len(lgas_gdf),
                geometry_type=str(lgas_gdf.geometry.geom_type.iloc[0]) if len(lgas_gdf) > 0 else 'unknown',
                crs=str(lgas_gdf.crs),
                file_path=str(self.processed_dir / "nigeria_lgas_unified.geojson")
            )
        
        return info


def main():
    """Example usage of the Boundary Manager"""
    
    # Initialize boundary manager
    boundary_manager = NigerianBoundaryManager()
    
    print("Nigerian Boundary Manager")
    print("=" * 40)
    
    # Download boundary data
    print("\n1. Downloading boundary data...")
    gadm_success = boundary_manager.download_gadm_boundaries()
    geo_states_success, geo_lgas_success = boundary_manager.download_geoboundaries()
    
    print(f"   GADM: {'✅' if gadm_success else '❌'}")
    print(f"   GeoBoundaries States: {'✅' if geo_states_success else '❌'}")
    print(f"   GeoBoundaries LGAs: {'✅' if geo_lgas_success else '❌'}")
    
    # Process and unify boundaries
    print("\n2. Processing and unifying boundaries...")
    states_gdf, lgas_gdf = boundary_manager.create_unified_boundaries()
    
    if states_gdf is not None:
        print(f"   ✅ States: {len(states_gdf)} records processed")
    if lgas_gdf is not None:
        print(f"   ✅ LGAs: {len(lgas_gdf)} records processed")
    
    # Display boundary information
    print("\n3. Boundary Information:")
    boundary_info = boundary_manager.get_boundary_info()
    
    for level, info in boundary_info.items():
        print(f"\n   {info.name}:")
        print(f"      Records: {info.record_count}")
        print(f"      Source: {info.source}")
        print(f"      CRS: {info.crs}")
        print(f"      File: {Path(info.file_path).name}")
    
    # Example spatial join (with mock data)
    print("\n4. Testing spatial join capability...")
    
    # Create sample points (Lagos, Abuja, Kano)
    sample_data = pd.DataFrame({
        'location': ['Lagos', 'Abuja', 'Kano'],
        'latitude': [6.5244, 9.0765, 12.0022],
        'longitude': [3.3792, 7.3986, 8.5920],
        'cases': [45, 23, 12]
    })
    
    # Perform spatial join
    joined_data = boundary_manager.spatial_join_data(
        sample_data, 'latitude', 'longitude', level='state'
    )
    
    if 'name' in joined_data.columns:
        print("   Spatial join successful!")
        print("   Sample results:")
        for _, row in joined_data.iterrows():
            state_name = row.get('name', 'Unknown')
            print(f"      {row['location']} → {state_name.title()} State")
    else:
        print("   Spatial join completed but no state names found")
    
    print(f"\n🎉 Boundary Manager setup complete!")
    print(f"   Data stored in: {boundary_manager.boundaries_dir}")

if __name__ == "__main__":
    main()