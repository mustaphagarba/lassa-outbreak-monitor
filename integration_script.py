"""
Lassa Fever Data Integration Pipeline
======================================

This script integrates the NCDC scraper with the boundary manager to create
geospatially-enabled datasets for analysis and visualization.

Usage:
    python integration_script.py [--max-files 50] [--force-download] [--skip-scraping]
"""

import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime
import pandas as pd
import geopandas as gpd
import json

# Import our modules
try:
    from ncdc_scraper import NCDCLassaScraper
    from boundary_manager import NigerianBoundaryManager
except ImportError as e:
    print(f"Error: Could not import required modules: {e}")
    print("Make sure ncdc_scraper.py and boundary_manager.py are in the same directory")
    sys.exit(1)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data/integration_log.txt'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class LassaDataIntegrator:
    """
    Integrates NCDC scraper output with boundary data to create
    geospatially-enabled Lassa fever datasets.
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Initialize managers
        self.scraper = NCDCLassaScraper()
        self.boundary_manager = NigerianBoundaryManager(data_dir=str(self.data_dir))
        
        # Output directories
        self.output_dir = self.data_dir / "integrated"
        self.output_dir.mkdir(exist_ok=True)
        
        logger.info("Initialized Lassa Data Integrator")
    
    def setup_boundaries(self, force_download: bool = False) -> bool:
        """
        Step 1: Download and process boundary data.
        
        Args:
            force_download: Force re-download even if files exist
            
        Returns:
            True if successful
        """
        logger.info("=" * 60)
        logger.info("STEP 1: Setting up boundary data")
        logger.info("=" * 60)
        
        try:
            # Check if boundaries already exist
            states_file = self.boundary_manager.processed_dir / "nigeria_states_unified.geojson"
            
            if states_file.exists() and not force_download:
                logger.info("Boundaries already exist. Loading...")
                states, lgas = self.boundary_manager.load_boundaries('both')
                if len(states) > 0:
                    logger.info(f"✅ Loaded {len(states)} states, {len(lgas)} LGAs")
                    return True
            
            # Download boundaries
            logger.info("Downloading boundary data...")
            gadm_success = self.boundary_manager.download_gadm_boundaries(force=force_download)
            geo_states, geo_lgas = self.boundary_manager.download_geoboundaries(force=force_download)
            
            if not (gadm_success or geo_states or geo_lgas):
                logger.error("❌ Failed to download any boundary data")
                return False
            
            # Process boundaries
            logger.info("Processing and unifying boundaries...")
            states_gdf, lgas_gdf = self.boundary_manager.create_unified_boundaries()
            
            if len(states_gdf) == 0:
                logger.error("❌ No state boundaries available after processing")
                return False
            
            logger.info(f"✅ Processed {len(states_gdf)} states, {len(lgas_gdf)} LGAs")
            
            # Validate
            validation = self.boundary_manager.validate_boundaries('state')
            logger.info(f"✅ Validation: {validation['valid_geometries']}/{validation['total_features']} valid geometries")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error setting up boundaries: {e}")
            return False
    
    def scrape_case_data(self, max_files: int = 50, skip_scraping: bool = False) -> tuple:
        """
        Step 2: Scrape NCDC data.
        
        Args:
            max_files: Maximum number of PDF reports to process
            skip_scraping: Skip scraping and use existing data
            
        Returns:
            Tuple of (weekly_df, state_level_df)
        """
        logger.info("=" * 60)
        logger.info("STEP 2: Scraping NCDC data")
        logger.info("=" * 60)
        
        try:
            # Check for existing data
            weekly_file = self.data_dir / "processed" / "lassa_fever_weekly_data.csv"
            state_file = self.data_dir / "processed" / "lassa_fever_state_level.csv"
            
            if skip_scraping and weekly_file.exists() and state_file.exists():
                logger.info("Using existing scraped data...")
                df_weekly = pd.read_csv(weekly_file)
                df_states = pd.read_csv(state_file)
                logger.info(f"✅ Loaded {len(df_weekly)} weekly records, {len(df_states)} state records")
                return df_weekly, df_states
            
            # Run scraper
            logger.info(f"Scraping up to {max_files} reports from NCDC...")
            df_weekly, df_states = self.scraper.scrape_all_data(max_files=max_files)
            
            if df_weekly.empty:
                logger.error("❌ No data scraped")
                return pd.DataFrame(), pd.DataFrame()
            
            logger.info(f"✅ Scraped {len(df_weekly)} weekly reports")
            
            if df_states.empty:
                logger.warning("⚠️  No state-level data extracted")
                logger.warning("    This may indicate PDF parsing issues")
                logger.warning("    You can still proceed with weekly aggregates")
            else:
                logger.info(f"✅ Extracted {len(df_states)} state-level records")
                logger.info(f"   States with data: {df_states['state'].nunique()}")
            
            return df_weekly, df_states
            
        except Exception as e:
            logger.error(f"❌ Error scraping data: {e}")
            return pd.DataFrame(), pd.DataFrame()
    
    def match_to_boundaries(self, df_states: pd.DataFrame) -> gpd.GeoDataFrame:
        """
        Step 3: Match state-level case data to boundaries.
        
        Args:
            df_states: State-level case data from scraper
            
        Returns:
            GeoDataFrame with matched geometries
        """
        logger.info("=" * 60)
        logger.info("STEP 3: Matching case data to boundaries")
        logger.info("=" * 60)
        
        try:
            if df_states.empty:
                logger.warning("⚠️  No state-level data to match")
                return gpd.GeoDataFrame()
            
            # Match to boundaries
            logger.info(f"Matching {len(df_states)} state records to boundaries...")
            geo_cases = self.boundary_manager.match_case_data_to_boundaries(
                df_states,
                state_col='state',
                boundary_level='state'
            )
            
            # Check results
            matched_count = len(geo_cases[geo_cases['geometry'].notna()])
            unmatched_count = len(geo_cases[geo_cases['geometry'].isna()])
            
            logger.info(f"✅ Matched: {matched_count} records")
            if unmatched_count > 0:
                logger.warning(f"⚠️  Unmatched: {unmatched_count} records")
                logger.warning("   Check the log above for suggestions")
            
            return geo_cases
            
        except Exception as e:
            logger.error(f"❌ Error matching to boundaries: {e}")
            return gpd.GeoDataFrame()
    
    def create_aggregated_datasets(self, geo_cases: gpd.GeoDataFrame) -> dict:
        """
        Step 4: Create aggregated datasets for analysis.
        
        Args:
            geo_cases: GeoDataFrame with matched case data
            
        Returns:
            Dictionary of aggregated datasets
        """
        logger.info("=" * 60)
        logger.info("STEP 4: Creating aggregated datasets")
        logger.info("=" * 60)
        
        datasets = {}
        
        try:
            if geo_cases.empty or geo_cases['geometry'].isna().all():
                logger.warning("⚠️  No geospatial data available for aggregation")
                return datasets
            
            # Filter to only matched records
            geo_cases_clean = geo_cases[geo_cases['geometry'].notna()].copy()
            
            # 1. Total cases by state (all time)
            logger.info("Creating state-level aggregates...")
            state_totals = geo_cases_clean.groupby('state').agg({
                'cases': 'sum',
                'week': 'count'
            }).reset_index()
            state_totals.columns = ['state', 'total_cases', 'report_count']
            
            # Merge with geometry
            states_gdf = self.boundary_manager.load_boundaries('state')
            if isinstance(states_gdf, tuple):
                states_gdf = states_gdf[0]
            
            # Normalize names for matching
            state_totals['_normalized'] = state_totals['state'].apply(
                self.boundary_manager._normalize_for_matching
            )
            states_gdf['_normalized'] = states_gdf['name'].apply(
                self.boundary_manager._normalize_for_matching
            )
            
            state_totals_geo = states_gdf.merge(
                state_totals,
                on='_normalized',
                how='left'
            ).drop(columns=['_normalized'])
            
            # Fill NaN with 0 for states with no cases
            state_totals_geo['total_cases'] = state_totals_geo['total_cases'].fillna(0)
            state_totals_geo['report_count'] = state_totals_geo['report_count'].fillna(0)
            
            datasets['state_totals'] = state_totals_geo
            logger.info(f"   ✅ State totals: {len(state_totals_geo)} states")
            
            # 2. Time series by state
            if 'year' in geo_cases_clean.columns and 'week' in geo_cases_clean.columns:
                logger.info("Creating time series data...")
                time_series = geo_cases_clean.groupby(['state', 'year', 'week']).agg({
                    'cases': 'sum'
                }).reset_index()
                
                datasets['time_series'] = time_series
                logger.info(f"   ✅ Time series: {len(time_series)} records")
            
            # 3. Annual summaries
            if 'year' in geo_cases_clean.columns:
                logger.info("Creating annual summaries...")
                annual = geo_cases_clean.groupby(['state', 'year']).agg({
                    'cases': 'sum'
                }).reset_index()
                annual.columns = ['state', 'year', 'annual_cases']
                
                datasets['annual_summary'] = annual
                logger.info(f"   ✅ Annual summary: {len(annual)} records")
            
            # 4. Recent activity (last 13 weeks)
            if 'year' in geo_cases_clean.columns and 'week' in geo_cases_clean.columns:
                logger.info("Creating recent activity dataset...")
                
                # Get most recent year-week combination
                geo_cases_clean['year_week'] = geo_cases_clean['year'] * 100 + geo_cases_clean['week']
                max_year_week = geo_cases_clean['year_week'].max()
                
                # Filter to last ~13 weeks (approximate quarter)
                recent = geo_cases_clean[geo_cases_clean['year_week'] > (max_year_week - 13)]
                
                recent_summary = recent.groupby('state').agg({
                    'cases': 'sum',
                    'week': 'count'
                }).reset_index()
                recent_summary.columns = ['state', 'recent_cases', 'recent_reports']
                
                # Merge with geometry
                recent_summary['_normalized'] = recent_summary['state'].apply(
                    self.boundary_manager._normalize_for_matching
                )
                
                recent_geo = states_gdf.merge(
                    recent_summary,
                    on='_normalized',
                    how='left'
                ).drop(columns=['_normalized'])
                
                recent_geo['recent_cases'] = recent_geo['recent_cases'].fillna(0)
                recent_geo['recent_reports'] = recent_geo['recent_reports'].fillna(0)
                
                datasets['recent_activity'] = recent_geo
                logger.info(f"   ✅ Recent activity: {len(recent_geo)} states")
            
            return datasets
            
        except Exception as e:
            logger.error(f"❌ Error creating aggregated datasets: {e}")
            return datasets
    
    def save_outputs(self, geo_cases: gpd.GeoDataFrame, 
                     aggregated: dict, df_weekly: pd.DataFrame) -> dict:
        """
        Step 5: Save all outputs.
        
        Args:
            geo_cases: Full geospatial case data
            aggregated: Dictionary of aggregated datasets
            df_weekly: Weekly summary data
            
        Returns:
            Dictionary of saved file paths
        """
        logger.info("=" * 60)
        logger.info("STEP 5: Saving outputs")
        logger.info("=" * 60)
        
        saved_files = {}
        
        try:
            # 1. Save full geospatial case data
            if not geo_cases.empty and not geo_cases['geometry'].isna().all():
                geo_cases_clean = geo_cases[geo_cases['geometry'].notna()]
                
                output_file = self.output_dir / "lassa_cases_geospatial.geojson"
                geo_cases_clean.to_file(output_file, driver='GeoJSON')
                saved_files['geospatial_cases'] = str(output_file)
                logger.info(f"   ✅ {output_file.name}")
                
                # Also save as CSV (without geometry for easier analysis)
                csv_file = self.output_dir / "lassa_cases_with_state_info.csv"
                geo_cases_clean.drop(columns=['geometry']).to_csv(csv_file, index=False)
                saved_files['cases_csv'] = str(csv_file)
                logger.info(f"   ✅ {csv_file.name}")
            
            # 2. Save aggregated datasets
            for name, dataset in aggregated.items():
                if isinstance(dataset, gpd.GeoDataFrame) and not dataset.empty:
                    geojson_file = self.output_dir / f"lassa_{name}.geojson"
                    dataset.to_file(geojson_file, driver='GeoJSON')
                    saved_files[f'{name}_geojson'] = str(geojson_file)
                    logger.info(f"   ✅ {geojson_file.name}")
                    
                    # Also save as CSV
                    csv_file = self.output_dir / f"lassa_{name}.csv"
                    dataset.drop(columns=['geometry']).to_csv(csv_file, index=False)
                    saved_files[f'{name}_csv'] = str(csv_file)
                    logger.info(f"   ✅ {csv_file.name}")
                    
                elif isinstance(dataset, pd.DataFrame) and not dataset.empty:
                    csv_file = self.output_dir / f"lassa_{name}.csv"
                    dataset.to_csv(csv_file, index=False)
                    saved_files[f'{name}_csv'] = str(csv_file)
                    logger.info(f"   ✅ {csv_file.name}")
            
            # 3. Save weekly data (reference)
            if not df_weekly.empty:
                weekly_file = self.output_dir / "lassa_weekly_summary.csv"
                df_weekly.to_csv(weekly_file, index=False)
                saved_files['weekly_summary'] = str(weekly_file)
                logger.info(f"   ✅ {weekly_file.name}")
            
            # 4. Save integration metadata
            metadata = {
                'integration_date': datetime.now().isoformat(),
                'files_created': saved_files,
                'data_summary': {
                    'total_weekly_reports': len(df_weekly) if not df_weekly.empty else 0,
                    'total_state_records': len(geo_cases) if not geo_cases.empty else 0,
                    'matched_records': len(geo_cases[geo_cases['geometry'].notna()]) if not geo_cases.empty else 0,
                    'states_with_data': geo_cases['state'].nunique() if not geo_cases.empty else 0,
                }
            }
            
            metadata_file = self.output_dir / "integration_metadata.json"
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
            saved_files['metadata'] = str(metadata_file)
            logger.info(f"   ✅ {metadata_file.name}")
            
            return saved_files
            
        except Exception as e:
            logger.error(f"❌ Error saving outputs: {e}")
            return saved_files
    
    def run_full_pipeline(self, max_files: int = 50, force_download: bool = False,
                         skip_scraping: bool = False) -> bool:
        """
        Run the complete integration pipeline.
        
        Args:
            max_files: Maximum PDF reports to process
            force_download: Force re-download of boundaries
            skip_scraping: Use existing scraped data
            
        Returns:
            True if successful
        """
        logger.info("\n" + "=" * 60)
        logger.info("LASSA FEVER DATA INTEGRATION PIPELINE")
        logger.info("=" * 60)
        logger.info(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        try:
            # Step 1: Setup boundaries
            if not self.setup_boundaries(force_download):
                logger.error("Pipeline failed at Step 1: Boundaries")
                return False
            
            # Step 2: Scrape data
            df_weekly, df_states = self.scrape_case_data(max_files, skip_scraping)
            if df_weekly.empty:
                logger.error("Pipeline failed at Step 2: Scraping")
                return False
            
            # Step 3: Match to boundaries
            geo_cases = self.match_to_boundaries(df_states)
            
            # Step 4: Create aggregates
            aggregated = self.create_aggregated_datasets(geo_cases)
            
            # Step 5: Save outputs
            saved_files = self.save_outputs(geo_cases, aggregated, df_weekly)
            
            # Summary
            logger.info("\n" + "=" * 60)
            logger.info("PIPELINE COMPLETED SUCCESSFULLY")
            logger.info("=" * 60)
            logger.info(f"\n📊 Data Summary:")
            logger.info(f"   Weekly reports: {len(df_weekly)}")
            logger.info(f"   State records: {len(df_states) if not df_states.empty else 0}")
            logger.info(f"   Matched records: {len(geo_cases[geo_cases['geometry'].notna()]) if not geo_cases.empty else 0}")
            
            logger.info(f"\n💾 Files created: {len(saved_files)}")
            logger.info(f"   Location: {self.output_dir}")
            
            logger.info(f"\n✅ Ready for Phase 2: Exploratory Analysis!")
            logger.info(f"   Use the files in {self.output_dir} for visualization\n")
            
            return True
            
        except Exception as e:
            logger.error(f"\n❌ Pipeline failed with error: {e}")
            return False


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Integrate NCDC Lassa fever data with geospatial boundaries'
    )
    parser.add_argument(
        '--max-files',
        type=int,
        default=50,
        help='Maximum number of PDF reports to process (default: 50)'
    )
    parser.add_argument(
        '--force-download',
        action='store_true',
        help='Force re-download of boundary data'
    )
    parser.add_argument(
        '--skip-scraping',
        action='store_true',
        help='Skip scraping and use existing data'
    )
    
    args = parser.parse_args()
    
    # Run pipeline
    integrator = LassaDataIntegrator()
    success = integrator.run_full_pipeline(
        max_files=args.max_files,
        force_download=args.force_download,
        skip_scraping=args.skip_scraping
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
