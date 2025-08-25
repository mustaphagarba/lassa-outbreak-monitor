import re
import requests
from pathlib import Path
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
import PyPDF2
from io import BytesIO
import time
import json
from typing import List, Dict, Optional
import logging
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class NCDCLassaScraper:
    
    
    def __init__(self):
        self.base_url = "https://ncdc.gov.ng"
        self.sitreps_url = "https://ncdc.gov.ng/diseases/sitreps/?cat=5&name=An%20update%20of%20Lassa%20fever%20outbreak%20in%20Nigeria"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        
        # Create data directory
        self.data_dir = Path("data")
        self.data_dir.mkdir(exist_ok=True)
        
        # Create subdirectories
        (self.data_dir / "raw_pdfs").mkdir(exist_ok=True)
        (self.data_dir / "processed").mkdir(exist_ok=True)
        
    def get_pdf_links(self) -> List[Dict]:
        
        logger.info("Fetching PDF links from NCDC...")
        
        try:
            response = self.session.get(self.sitreps_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all PDF links
            pdf_links = []
            rows = soup.find_all('tr')
            
            for row in rows:
                cells = row.find_all('td')
                if len(cells) >= 2:
                    title_cell = cells[1]  # Second column has the title
                    link_cell = cells[2] if len(cells) > 2 else cells[1]  # Third column has link
                    
                    # Extract title
                    title = title_cell.get_text(strip=True)
                    if 'Lassa fever' in title and 'Week' in title:
                        
                        # Extract week and year from title
                        week_match = re.search(r'Week (\d+)', title)
                        if week_match:
                            week_num = int(week_match.group(1))
                            
                            # Extract PDF link
                            link_tag = link_cell.find('a')
                            if link_tag and link_tag.get('href'):
                                pdf_url = self.base_url + link_tag['href']
                                
                                pdf_links.append({
                                    'title': title,
                                    'week': week_num,
                                    'pdf_url': pdf_url,
                                    'year_estimated': self._estimate_year_from_context(len(pdf_links))
                                })
            
            logger.info(f"Found {len(pdf_links)} PDF reports")
            return pdf_links
            
        except Exception as e:
            logger.error(f"Error fetching PDF links: {e}")
            return []
    
    def _estimate_year_from_context(self, index: int) -> int:
        
        current_year = datetime.now().year
        # Approximate: ~52 reports per year, but account for gaps
        years_back = index // 45  # Conservative estimate
        return current_year - years_back
    
    def download_pdf(self, pdf_url: str, filename: str) -> Optional[bytes]:
        
        try:
            logger.info(f"Downloading {filename}...")
            response = self.session.get(pdf_url, timeout=30)
            response.raise_for_status()
            
            # Save to raw_pdfs directory
            pdf_path = self.data_dir / "raw_pdfs" / filename
            with open(pdf_path, 'wb') as f:
                f.write(response.content)
            
            return response.content
        
        except Exception as e:
            logger.error(f"Error downloading {filename}: {e}")
            return None
    
    def extract_text_from_pdf(self, pdf_content: bytes) -> str:
        
        try:
            pdf_reader = PyPDF2.PdfReader(BytesIO(pdf_content))
            text = ""
            
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            
            return text
        
        except Exception as e:
            logger.error(f"Error extracting text from PDF: {e}")
            return ""
    
    def parse_lassa_data(self, text: str, week: int, year: int) -> Dict:
        
        data = {
            'week': week,
            'year': year,
            'total_cases': None,
            'confirmed_cases': None,
            'deaths': None,
            'case_fatality_rate': None,
            'affected_states': None,
            'affected_lgas': None,
            'new_cases_week': None,
            'new_deaths_week': None
        }
        
        try:
            # Clean text
            text = re.sub(r'\s+', ' ', text.replace('\n', ' '))
            
            # Extract total cases (various patterns)
            total_cases_patterns = [
                r'total\s+of\s+(\d+)\s+cases',
                r'(\d+)\s+total\s+cases',
                r'total\s+cases:\s*(\d+)',
                r'cumulative\s+cases:\s*(\d+)'
            ]
            
            for pattern in total_cases_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    data['total_cases'] = int(match.group(1))
                    break
            
            # Extract confirmed cases
            confirmed_patterns = [
                r'(\d+)\s+confirmed\s+cases',
                r'confirmed\s+cases:\s*(\d+)',
                r'confirmed:\s*(\d+)'
            ]
            
            for pattern in confirmed_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    data['confirmed_cases'] = int(match.group(1))
                    break
            
            # Extract deaths
            death_patterns = [
                r'(\d+)\s+deaths?',
                r'deaths?:\s*(\d+)',
                r'fatalities:\s*(\d+)',
                r'died:\s*(\d+)'
            ]
            
            for pattern in death_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    data['deaths'] = int(match.group(1))
                    break
            
            # Extract CFR (Case Fatality Rate)
            cfr_patterns = [
                r'case\s+fatality\s+rate\s*[:\s]*(\d+\.?\d*)%?',
                r'cfr\s*[:\s]*(\d+\.?\d*)%?',
                r'fatality\s+rate\s*[:\s]*(\d+\.?\d*)%?'
            ]
            
            for pattern in cfr_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    data['case_fatality_rate'] = float(match.group(1))
                    break
            
            # Extract affected states count
            states_patterns = [
                r'(\d+)\s+states?\s+affected',
                r'affected\s+states?:\s*(\d+)',
                r'(\d+)\s+states?\s+reported'
            ]
            
            for pattern in states_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    data['affected_states'] = int(match.group(1))
                    break
            
            # Extract affected LGAs count
            lga_patterns = [
                r'(\d+)\s+lgas?\s+affected',
                r'affected\s+lgas?:\s*(\d+)',
                r'(\d+)\s+local\s+government\s+areas?'
            ]
            
            for pattern in lga_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    data['affected_lgas'] = int(match.group(1))
                    break
            
            # Extract weekly new cases
            new_cases_patterns = [
                r'(\d+)\s+new\s+cases?\s+in\s+week',
                r'week\s+\d+[:\s]*(\d+)\s+new\s+cases?',
                r'(\d+)\s+cases?\s+reported\s+in\s+week'
            ]
            
            for pattern in new_cases_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    data['new_cases_week'] = int(match.group(1))
                    break
        
        except Exception as e:
            logger.error(f"Error parsing data for week {week}: {e}")
        
        return data
    
    def scrape_all_data(self, max_files: int = 50) -> pd.DataFrame:
        
        logger.info("Starting NCDC Lassa fever data scraping...")
        
        # Get all PDF links
        pdf_links = self.get_pdf_links()
        
        if not pdf_links:
            logger.error("No PDF links found!")
            return pd.DataFrame()
        
        # Limit number of files to process
        pdf_links = pdf_links[:max_files]
        
        all_data = []
        
        for i, link in enumerate(pdf_links):
            logger.info(f"Processing {i+1}/{len(pdf_links)}: Week {link['week']}")
            
            # Create filename
            filename = f"lassa_week_{link['week']}_{link['year_estimated']}.pdf"
            
            # Download PDF
            pdf_content = self.download_pdf(link['pdf_url'], filename)
            
            if pdf_content:
                # Extract text
                text = self.extract_text_from_pdf(pdf_content)
                
                if text:
                    
                    parsed_data = self.parse_lassa_data(text, link['week'], link['year_estimated'])
                    parsed_data['pdf_url'] = link['pdf_url']
                    parsed_data['title'] = link['title']
                    
                    all_data.append(parsed_data)
                
            
            time.sleep(1)
        
        
        df = pd.DataFrame(all_data)
        
        if not df.empty:
            
            df = df.sort_values(['year', 'week'], ascending=[False, False])
            
            
            df['epi_date'] = df.apply(self._calculate_epi_date, axis=1)
            
            output_file = self.data_dir / "processed" / "lassa_fever_weekly_data.csv"
            df.to_csv(output_file, index=False)
            logger.info(f"Saved {len(df)} records to {output_file}")
            
            
            metadata = {
                'scrape_date': datetime.now().isoformat(),
                'total_reports': len(df),
                'date_range': f"{df['year'].min()}-W{df['week'].min()} to {df['year'].max()}-W{df['week'].max()}",
                'data_fields': list(df.columns)
            }
            
            with open(self.data_dir / "processed" / "scrape_metadata.json", 'w') as f:
                json.dump(metadata, f, indent=2)
        
        return df
    
    def _calculate_epi_date(self, row) -> str:
        
        try:
            
            year = int(row['year'])
            week = int(row['week'])
            
            # approximation - will do more research later to refine
            jan_1 = datetime(year, 1, 1)
            days_to_add = (week - 1) * 7
            epi_date = jan_1 + timedelta(days=days_to_add)
            
            return epi_date.strftime('%Y-%m-%d')
        
        except:
            return ""
    
    def create_summary_stats(self, df: pd.DataFrame):
        
        if df.empty:
            return
        
        
        annual_summary = df.groupby('year').agg({
            'total_cases': 'max',
            'confirmed_cases': 'max', 
            'deaths': 'max',
            'case_fatality_rate': 'mean',
            'affected_states': 'max',
            'affected_lgas': 'max'
        }).reset_index()
        
        annual_summary.to_csv(
            self.data_dir / "processed" / "lassa_annual_summary.csv", 
            index=False
        )
        
        # Monthly aggregations (approximate)
        df['month'] = pd.to_datetime(df['epi_date'], errors='coerce').dt.month
        monthly_summary = df.groupby(['year', 'month']).agg({
            'new_cases_week': 'sum',
            'new_deaths_week': 'sum'
        }).reset_index()
        
        monthly_summary.to_csv(
            self.data_dir / "processed" / "lassa_monthly_summary.csv",
            index=False
        )
        
        logger.info("Created summary statistics files")

def main():
    
    scraper = NCDCLassaScraper()
    
    # Scrape data (start with 50 most recent reports)
    df = scraper.scrape_all_data(max_files=50)
    
    if not df.empty:
        print(f"\nSuccessfully scraped {len(df)} Lassa fever reports!")
        print(f"Date range: {df['year'].min()}-{df['year'].max()}")
        print(f"Data saved to: data/processed/")
        
        # Create summary statistics
        scraper.create_summary_stats(df)
        
        # Show sample of data
        print("\nSample of extracted data:")
        print(df[['year', 'week', 'total_cases', 'deaths', 'affected_states']].head())
        
    else:
        print("No data was successfully extracted")

if __name__ == "__main__":
    main()