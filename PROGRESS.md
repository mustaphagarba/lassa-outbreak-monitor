# Lassa Fever Hotspot Prediction Dashboard - Progress Report

**Last Updated:** January 2025  
**Status:** Phase 1 (Data Cleaning & Integration) - ~70% Complete

---

## Executive Summary

We are building a geospatial data pipeline for Lassa fever outbreak prediction in Nigeria. The project is progressing through Phase 1, with core infrastructure now in place for data collection, boundary management, and integration.

**Current Focus:** Completing Phase 1 (Data Cleaning & Integration)  
**Next Phase:** Phase 2 (Exploratory Analysis & Visualization)

---

## Phase 1: Data Cleaning & Integration (70% Complete)

### ✅ Completed

#### 1. **NCDC Data Scraper** (Complete)
- **File:** `ncdc_scraper.py`
- **Status:** ✅ Fully implemented and enhanced
- **Features:**
  - Downloads weekly situation reports from NCDC website
  - Extracts weekly aggregate data (total cases, deaths, CFR, affected states/LGAs)
  - **NEW:** Extracts state-level case data for geospatial matching
  - PDF text extraction with regex-based parsing
  - Handles multiple PDF format variations
  - Caches downloaded PDFs to avoid re-downloading
  - Generates summary statistics (annual, monthly aggregates)
  - Outputs:
    - `lassa_fever_weekly_data.csv` - Weekly summaries
    - `lassa_fever_state_level.csv` - State-by-state case counts
    - `lassa_fever_annual_summary.csv` - Yearly aggregates
    - `scrape_metadata.json` - Scraping metadata

**Known Limitation:** State extraction via regex depends on PDF text extraction quality. Some PDFs may have formatting variations that require pattern refinement.

#### 2. **Nigerian Boundary Manager** (Complete)
- **File:** `boundary_manager.py`
- **Status:** ✅ Production-ready implementation
- **Features:**
  - Downloads from dual sources (GADM v4.1 + GeoBoundaries) with fallback logic
  - Processes and unifies state (ADM1) and LGA (ADM2) boundaries
  - Nigerian-specific name standardization (handles FCT variants, diacritics, etc.)
  - **NEW Methods for Scraper Integration:**
    - `match_case_data_to_boundaries()` - Matches state names to geometries
    - `spatial_join_data()` - Joins lat/lon points to administrative boundaries
    - `get_state_lga_hierarchy()` - Returns state→LGA mapping
    - `validate_boundaries()` - Quality checks on boundary data
    - `create_centroid_dataset()` - Generates center points for visualization
    - `export_for_analysis()` - Exports in GeoJSON/Shapefile/GeoPackage
  - Fuzzy name matching with suggestion engine for unmatched locations
  - Metadata tracking with file hashes for change detection
  - Graceful error handling (creates empty datasets if files missing)
  - Outputs:
    - `nigeria_states_unified.geojson` - Processed state boundaries
    - `nigeria_lgas_unified.geojson` - Processed LGA boundaries
    - `boundary_metadata.json` - Metadata about boundary sources

#### 3. **Data Integration Pipeline** (Complete)
- **File:** `integrate_data.py`
- **Status:** ✅ Fully automated end-to-end pipeline
- **Features:**
  - 5-step automated workflow:
    1. Setup/validate boundaries
    2. Scrape NCDC case data
    3. Match cases to geographic boundaries
    4. Create aggregated analysis datasets
    5. Save outputs in multiple formats
  - Intelligent caching (skips re-downloads/re-scraping when data exists)
  - Comprehensive logging to file + console
  - Command-line arguments for flexibility
  - Generates multiple output formats (GeoJSON + CSV)
  - Outputs:
    - `lassa_cases_geospatial.geojson` - Full case data with geometries
    - `lassa_state_totals.geojson` - Aggregated by state (all-time)
    - `lassa_recent_activity.geojson` - Last ~13 weeks by state
    - `lassa_time_series.csv` - State × Week × Cases
    - `lassa_annual_summary.csv` - State × Year × Cases
    - `integration_metadata.json` - Pipeline metadata
  - Usage:
    ```bash
    python integrate_data.py                    # Default (50 PDFs)
    python integrate_data.py --max-files 100   # Process more PDFs
    python integrate_data.py --skip-scraping    # Use existing data
    python integrate_data.py --force-download   # Re-download boundaries
    ```

### 🔄 In Progress

#### 1. **Data Quality Validation**
- Status: 🔄 Partial (boundary validation in place, scraper output validation needed)
- Next: Create validation notebook to check:
  - State name matching success rate
  - Data completeness per year
  - Outlier detection (unusually high/low case counts)
  - Temporal continuity checks

#### 2. **Additional Data Source Integration**
- Status: 🔄 Planned but not yet implemented
- Components needed:
  - Climate data downloader (ERA5 via CDS API)
  - Population data (WorldPop integration)
  - Land-use data (ESA Land Cover)
  - Infrastructure for joining these to case data

### ❌ Not Yet Started

#### 1. **Database Setup**
- PostgreSQL schema for time-series storage
- Efficient querying for dashboard backend
- Data warehouse design

---

## Phase 2: Exploratory Analysis & Visualization (0% - Ready to Start)

### Planned Activities

#### 1. **Exploratory Data Analysis Notebook**
- Static maps of historical outbreaks (state/LGA level)
- Correlation analysis: cases vs climate variables
- Time series decomposition (trend, seasonality)
- Box plots and distribution analysis by state
- Heatmaps of outbreak intensity over time

#### 2. **Interactive Visualization Prototypes**
- Choropleth maps (folium/plotly) showing case incidence
- Time slider for temporal analysis
- Hotspot identification using spatial clustering
- Comparison between years/seasons

---

## Phase 3: Modeling (0% - Planned)

### Planned Modeling Tasks

1. **Exploratory Model Development**
   - Logistic regression (baseline)
   - Random forest classifier
   - Gradient boosting models

2. **Evaluation Metrics**
   - Accuracy, precision, recall, F1
   - ROC/AUC curves
   - Cross-validation (k-fold)
   - Spatial cross-validation (leave-one-location-out)

3. **Feature Engineering**
   - Temporal features (seasonal indicators, lags)
   - Climate features (rolling averages, anomalies)
   - Population density interactions
   - LGA-level spatial features

---

## Phase 4: Dashboard Development (0% - Planned)

### Dashboard Prototype
- Streamlit application with:
  - Real-time case tracking map
  - Risk hotspot visualization
  - Time-series trends by state
  - Historical comparison views
  - Forecast/prediction display
  - Export functionality

---

## File Structure (Current)

```
lassa-outbreak-monitor/
│
├── ncdc_scraper.py                    # ✅ NCDC data scraper (enhanced)
├── boundary_manager.py                # ✅ Geospatial boundary manager (production-ready)
├── integrate_data.py                  # ✅ Integration pipeline
├── PROGRESS.md                        # This file
├── README.md                          # Project overview
│
├── data/
│   ├── raw_pdfs/                      # Downloaded NCDC reports
│   ├── processed/                     # Scraped data outputs
│   │   ├── lassa_fever_weekly_data.csv
│   │   ├── lassa_fever_state_level.csv
│   │   └── scrape_metadata.json
│   ├── boundaries/
│   │   ├── raw/                       # Downloaded boundary files
│   │   ├── processed/                 # Unified geospatial data
│   │   │   ├── nigeria_states_unified.geojson
│   │   │   ├── nigeria_lgas_unified.geojson
│   │   │   └── boundary_metadata.json
│   │   └── cache/
│   └── integrated/                    # Final outputs from integration pipeline
│       ├── lassa_cases_geospatial.geojson
│       ├── lassa_state_totals.geojson
│       ├── lassa_recent_activity.geojson
│       ├── lassa_time_series.csv
│       ├── lassa_annual_summary.csv
│       └── integration_metadata.json
│
├── notebooks/                         # 📋 Ready for Phase 2
│   ├── 01_exploratory_analysis.ipynb  # (To be created)
│   └── 02_visualization_prototypes.ipynb # (To be created)
│
├── src/                               # 📋 Ready for Phase 3
│   └── modeling/                      # (To be created)
│
└── dashboards/                        # 📋 Ready for Phase 4
    └── streamlit_app.py               # (To be created)
```

---

## Key Technical Decisions

### 1. **Dual-Source Boundary Strategy**
- Downloads from both GADM and GeoBoundaries
- Prefers GADM (more detailed), falls back to GeoBoundaries if needed
- Ensures coverage even if one source fails

### 2. **Fuzzy Name Matching**
- Normalizes state names (lowercase, removes special chars, handles variations)
- Provides suggestions for unmatched records
- Logs all mismatches for manual review

### 3. **Caching Strategy**
- Boundaries cached locally (fast re-runs)
- PDFs cached to avoid re-downloading
- Metadata tracked with file hashes

### 4. **Modular Design**
- Scraper and boundary manager are independent
- Integration pipeline orchestrates them
- Easy to extend with new data sources

---

## Dependencies

### Core Libraries
```
pandas>=1.0              # Data manipulation
geopandas>=0.10         # Geospatial operations
requests>=2.25          # HTTP requests for downloading
shapely>=1.7            # Geometry operations
fiona>=1.8              # Vector data I/O
folium>=0.12            # Web mapping
plotly>=5.0             # Interactive visualizations
scikit-learn>=0.24      # Machine learning (Phase 3)
streamlit>=1.0          # Dashboard (Phase 4)
```

---

## Known Issues & Workarounds

### 1. **PDF Text Extraction Variability**
- **Issue:** Different NCDC report formats extract differently
- **Current Workaround:** Multiple regex patterns for common variations
- **Solution:** Manual review and pattern refinement for each new format variant

### 2. **State Name Variations**
- **Issue:** PDFs sometimes use abbreviated names (e.g., "Akwa-Ibom" vs "Akwa Ibom")
- **Current Workaround:** Name standardization mapping in boundary manager
- **Solution:** Comprehensive mapping table maintained and expanded as needed

### 3. **Missing LGA-Level Data**
- **Issue:** PDFs often don't include detailed LGA-level breakdowns
- **Current Status:** Aggregating at state level; LGA-level may require manual data entry
- **Mitigation:** State-level analysis provides sufficient granularity for initial phases

---

## Testing Strategy

### Phase 1 Testing (Current)
- ✅ Boundary download and processing (tested)
- ✅ Name matching and fuzzy logic (tested with sample data)
- 🔄 Scraper output quality (needs validation notebook)

### Phase 2 Testing (Planned)
- Visual inspection of maps
- Statistical validation of aggregations
- Correlation checks with known outbreak patterns

### Phase 3+ Testing (Future)
- Model cross-validation
- Backtesting on historical data
- Sensitivity analysis

---

## Next Immediate Tasks (Priority Order)

### 1. **Run Integration Pipeline** (HIGH)
```bash
python integrate_data.py --max-files 50
```
- Generates all Phase 1 outputs
- Identifies any data quality issues
- Creates datasets for Phase 2

### 2. **Validate Scraper Output** (HIGH)
- Check state name matching success rate
- Review log for unmatched states
- Identify patterns needing refinement

### 3. **Create Phase 2 Exploration Notebook** (MEDIUM)
- Load integrated data
- Create basic maps
- Analyze state-level trends
- Check for obvious data issues

### 4. **Build Climate Data Integration** (MEDIUM)
- ERA5 API connection
- Temporal joining to case data
- Validation of merged datasets

### 5. **Schema Planning** (MEDIUM)
- Design PostgreSQL schema for production
- Plan data warehouse structure
- Prepare for dashboard backend

---

## Collaboration Notes



---

## Resources

- **NCDC Website:** https://ncdc.gov.ng
- **GADM Boundaries:** https://gadm.org
- **GeoBoundaries:** https://www.geoboundaries.org
- **ERA5 Climate Data:** https://cds.climate.copernicus.eu
- **WorldPop:** https://www.worldpop.org

---

## Glossary

- **ADM1/ADM2:** Administrative divisions (states and LGAs)
- **CFR:** Case Fatality Rate
- **Geojson:** Geographic JSON format for features with geometries
- **Shapefile:** Traditional GIS vector data format
- **Spatial Join:** Joining data based on geographic overlap/containment
- **CRS:** Coordinate Reference System (e.g., EPSG:4326 = WGS84)

---

## Questions or Issues?

Document any blockers or questions here as work progresses.