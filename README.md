# Lassa Fever Hotspot Prediction Dashboard

## Project Overview
This project builds a geospatial data pipeline and predictive dashboard for tracking and forecasting Lassa fever outbreaks in Nigeria. Using case data from the Nigeria Centre for Disease Control (NCDC) combined with climate, population, and land-use datasets, the dashboard identifies outbreak hotspots and provides insights for targeted interventions.

The project aligns with public health priorities in early warning systems, spatial epidemiology, and real-time risk mapping.

## Objectives
- Map historical Lassa fever cases across Nigeria at state/LGA level.
- Integrate climate, land-use, and population data to compute outbreak risk scores.
- Build a predictive model to forecast outbreak hotspots.
- Develop an interactive dashboard for real-time visualization and decision-making.

## Data Sources
- NCDC Weekly Situation Reports – Lassa fever case data.
- Climate Data – Copernicus ERA5 (rainfall, temperature, humidity).
- Land Use Data – ESA Land Cover maps (agricultural zones, forest cover).
- Population Data – WorldPop (settlement-level population density).
- Geospatial Boundaries – OpenStreetMap & GADM shapefiles.

## Tools & Technologies
- Python: pandas, geopandas, scikit-learn, folium, plotly
- GIS Tools: QGIS (for validation and visualization)
- Dashboard: Streamlit
- Data Management: PostgreSQL

## Project Structure
```
lassa-fever-hotspot-dashboard/
│
├── data/               
├── notebooks/          
├── src/                
├── dashboards/         
├── outputs/            
├── docs/               
└── README.md           
```

## Methodology
1. Data Cleaning & Integration  
   - Clean NCDC case reports into structured time-series datasets.  
   - Join with climate and land-use data using geopandas.  

2. Exploratory Analysis  
   - Map historical outbreaks by LGA/state.  
   - Correlate cases with climate and land-use variables.  

3. Modeling  
   - Train a predictive model (logistic regression, random forest).  
   - Evaluate with accuracy, ROC curves, and cross-validation.  

4. Dashboard Development  
   - Build interactive maps with folium or plotly.  
   - Create a Streamlit dashboard for dynamic hotspot visualization.  

## Outputs
- Interactive dashboard – map of outbreak hotspots with time slider and risk forecasts.  
- Static maps and figures – choropleths of Lassa fever incidence.  
- Predictive insights – risk zones for early warning and resource pre-positioning.  
- Policy brief (PDF) – short report summarizing findings for decision-makers.  

## Relevance
This project demonstrates the use of GIS and data analytics in health emergency preparedness, directly supporting priorities such as:  
- Predictive epidemic surveillance  
- Risk mapping for targeted interventions  
- Integration of climate and population data into health response strategies  

It showcases technical expertise in data integration, GIS analysis, predictive modeling, and dashboard design — skills critical for GIS & Data Analytics Specialist roles in public health and development.

## Next Steps
- Add additional climate-health datasets for validation.  
- Deploy dashboard online (Streamlit Cloud or GitHub Pages for folium maps).  
- Explore integration with open-source HIS systems for interoperability.  
