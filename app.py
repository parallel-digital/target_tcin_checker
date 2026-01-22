"""
Target TCIN Indexing Checker - Streamlit App
A web-based tool for checking if TCINs appear in Target.com search results

Installation Files Needed:
1. app.py (this file)
2. requirements.txt
3. packages.txt

For Streamlit Cloud deployment, create these additional files in your repo:

=== packages.txt ===
chromium
chromium-driver

=== requirements.txt ===
streamlit
selenium==4.15.2
pandas
beautifulsoup4

Run locally:
streamlit run app.py
"""

import streamlit as st
import pandas as pd
import re
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import subprocess
import os

# Page configuration
st.set_page_config(
    page_title="Target TCIN Checker",
    page_icon="🎯",
    layout="wide"
)

# Custom CSS
st.markdown("""
    <style>
    .main {
        padding: 2rem;
    }
    .stButton>button {
        background-color: #CC0000;
        color: white;
        font-weight: bold;
        border-radius: 8px;
        padding: 0.5rem 2rem;
        border: none;
    }
    .stButton>button:hover {
        background-color: #B30000;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 8px;
        padding: 1rem;
        color: #155724;
    }
    .info-box {
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        border-radius: 8px;
        padding: 1rem;
        color: #0c5460;
    }
    </style>
""", unsafe_allow_html=True)

def init_driver():
    """Initialize Selenium WebDriver with Chromium for Streamlit Cloud"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('--disable-extensions')
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.add_argument('--single-process')
    chrome_options.add_argument('--disable-dev-tools')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    try:
        # For Streamlit Cloud - use system chromium
        chrome_options.binary_location = "/usr/bin/chromium"
        
        # Find chromedriver
        chromedriver_path = "/usr/bin/chromedriver"
        
        # If not found, try chromium-driver
        if not os.path.exists(chromedriver_path):
            chromedriver_path = "/usr/bin/chromium-driver"
        
        # Create service
        service = Service(executable_path=chromedriver_path)
        driver = webdriver.Chrome(service=service, options=chrome_options)
        return driver, None
        
    except Exception as e:
        error_msg = f"Browser initialization error: {str(e)}"
        return None, error_msg

def search_target_keyword(driver, keyword, max_pages, progress_bar, status_text, max_retries=2):
    """Search Target for a keyword and extract TCINs with retry logic"""
    all_tcins = []
    
    for page in range(1, max_pages + 1):
        retry_count = 0
        success = False
        
        while retry_count <= max_retries and not success:
            try:
                offset = (page - 1) * 24
                url = f"https://www.target.com/s?searchTerm={keyword}&Nao={offset}"
                
                if retry_count > 0:
                    status_text.text(f"🔄 Retrying '{keyword}' - Page {page}/{max_pages} (Attempt {retry_count + 1})...")
                else:
                    status_text.text(f"🔍 Searching '{keyword}' - Page {page}/{max_pages}...")
                
                driver.get(url)
                
                # Wait for products to load
                wait = WebDriverWait(driver, 15)
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-test="product-card"], a[href*="/p/"]')))
                time.sleep(2)
                
                # Extract TCINs from ONLY the main search results grid
                # Find the main product grid container
                try:
                    # Target uses different selectors for the main search grid
                    product_cards = driver.find_elements(By.CSS_SELECTOR, '[data-test="product-card"]')
                    
                    unique_tcins = []
                    for card in product_cards:
                        try:
                            # Get the product link from each card
                            link = card.find_element(By.CSS_SELECTOR, 'a[href*="/p/"]')
                            href = link.get_attribute('href')
                            
                            # Extract TCIN from the URL
                            match = re.search(r'/A-(\d+)', href)
                            if match:
                                tcin = match.group(1)
                                if tcin not in unique_tcins:
                                    unique_tcins.append(tcin)
                        except:
                            continue
                    
                    # If no product cards found, fall back to scanning limited section
                    if len(unique_tcins) == 0:
                        # Try to find the main results section only
                        page_html = driver.page_source
                        
                        # Split by common recommendation section markers
                        main_section = page_html.split('Recommended for you')[0] if 'Recommended for you' in page_html else page_html
                        main_section = main_section.split('Sponsored')[0] if 'Sponsored' in main_section else main_section
                        
                        tcin_pattern = r'/p/[^/]+/-/A-(\d+)'
                        found_tcins = re.findall(tcin_pattern, main_section)
                        unique_tcins = list(dict.fromkeys(found_tcins))[:24]  # Limit to 24 (one page)
                        
                except Exception as e:
                    # Fallback to original method with limit
                    page_html = driver.page_source
                    tcin_pattern = r'/p/[^/]+/-/A-(\d+)'
                    found_tcins = re.findall(tcin_pattern, page_html)
                    unique_tcins = list(dict.fromkeys(found_tcins))[:24]
                
                # Add with position info
                for idx, tcin in enumerate(unique_tcins):
                    position = offset + idx + 1
                    all_tcins.append({
                        'tcin': tcin,
                        'position': position,
                        'page': page
                    })
                
                # Update progress
                progress = page / max_pages
                progress_bar.progress(progress)
                
                success = True
                
                # Stop if fewer products than expected
                if len(unique_tcins) < 24:
                    break
                    
                time.sleep(1.5)
                
            except Exception as e:
                retry_count += 1
                if retry_count > max_retries:
                    st.warning(f"⚠️ Failed after {max_retries + 1} attempts on page {page} for '{keyword}': {str(e)}")
                    return all_tcins  # Return what we have so far
                else:
                    time.sleep(3)  # Wait before retry
        
        if not success:
            break
    
    return all_tcins

def main():
    # Header
    st.title("🎯 Target TCIN Indexing Checker")
    st.markdown("**Check if your TCINs appear in Target.com search results across multiple keywords and pages**")
    
    # Setup instructions in expander
    with st.expander("📦 Setup Instructions (For Streamlit Cloud)", expanded=False):
        st.markdown("""
        ### Required Files for Deployment:
        
        **1. Create `packages.txt`:**
        ```
        chromium
        chromium-driver
        ```
        
        **2. Create `requirements.txt`:**
        ```
        streamlit
        selenium==4.15.2
        pandas
        beautifulsoup4
        ```
        
        **3. Push all files to GitHub:**
        - app.py
        - packages.txt
        - requirements.txt
        
        **4. Deploy on Streamlit Cloud:**
        - Go to share.streamlit.io
        - Connect your GitHub repo
        - Deploy!
        """)
    
    # Sidebar for inputs
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        st.subheader("TCINs")
        tcins_input = st.text_area(
            "Enter TCINs (one per line)",
            value="23980215\n23980216",
            height=150,
            help="Enter Target TCIN numbers, one per line"
        )
        
        st.subheader("Keywords")
        keywords_input = st.text_area(
            "Enter Keywords (one per line)",
            value="good2grow\ngood to grow\njuice box\nkids drinks\napple juice\nfruit punch",
            height=200,
            help="Enter search keywords, one per line"
        )
        
        max_pages = st.slider(
            "Max Pages per Keyword",
            min_value=1,
            max_value=10,
            value=3,
            help="How many pages of search results to check for each keyword"
        )
        
        st.markdown("---")
        
        run_search = st.button("🔍 Check Indexing", use_container_width=True)
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("""
        <div class="info-box">
            <h4>📋 How to Use:</h4>
            <ol>
                <li>Enter your TCINs in the sidebar (one per line)</li>
                <li>Enter keywords to search (one per line)</li>
                <li>Set how many pages to check per keyword</li>
                <li>Click "Check Indexing" and wait for results</li>
                <li>Download results as CSV</li>
            </ol>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        # Parse inputs
        tcin_list = [t.strip() for t in tcins_input.split('\n') if t.strip()]
        keyword_list = [k.strip() for k in keywords_input.split('\n') if k.strip()]
        
        st.metric("TCINs to Check", len(tcin_list))
        st.metric("Keywords", len(keyword_list))
        st.metric("Total Searches", len(keyword_list) * max_pages)
    
    # Run search
    if run_search:
        if not tcin_list or not keyword_list:
            st.error("⚠️ Please enter at least one TCIN and one keyword")
            return
        
        st.markdown("---")
        st.subheader("🔄 Search Progress")
        
        # Progress tracking
        overall_progress = st.progress(0)
        status_text = st.empty()
        log_container = st.expander("📊 Detailed Logs", expanded=True)
        
        results_data = {}
        driver = None
        
        try:
            # Initialize driver
            with log_container:
                st.write("🌐 Initializing browser...")
            
            driver, error = init_driver()
            
            if error or not driver:
                st.error(f"""
                ❌ **Failed to initialize browser.**
                
                **Error:** {error if error else 'Unknown error'}
                
                **For Streamlit Cloud, make sure you have:**
                1. A file called `packages.txt` with:
                   ```
                   chromium
                   chromium-driver
                   ```
                2. A file called `requirements.txt` with:
                   ```
                   streamlit
                   selenium==4.15.2
                   pandas
                   beautifulsoup4
                   ```
                
                **For local deployment:**
                - Install Chrome browser
                - Run: `pip install selenium webdriver-manager pandas beautifulsoup4 streamlit`
                """)
                return
            
            with log_container:
                st.success("✅ Browser initialized successfully!")
            
            # Search each keyword
            for idx, keyword in enumerate(keyword_list):
                with log_container:
                    st.write(f"\n**Searching: {keyword}**")
                
                page_progress = st.progress(0)
                
                # Try to search, recreate driver if it fails
                try:
                    search_results = search_target_keyword(
                        driver, keyword, max_pages, page_progress, status_text
                    )
                except Exception as e:
                    with log_container:
                        st.warning(f"⚠️ Browser crashed, reinitializing... ({str(e)})")
                    
                    # Close old driver
                    try:
                        driver.quit()
                    except:
                        pass
                    
                    # Create new driver
                    driver, error = init_driver()
                    if error or not driver:
                        st.error(f"❌ Failed to reinitialize browser: {error}")
                        break
                    
                    # Retry this keyword
                    search_results = search_target_keyword(
                        driver, keyword, max_pages, page_progress, status_text
                    )
                
                results_data[keyword] = search_results
                
                with log_container:
                    st.success(f"✅ Found {len(search_results)} total products for '{keyword}'")
                
                # Update overall progress
                overall_progress.progress((idx + 1) / len(keyword_list))
                
                # Delay between keywords
                if idx < len(keyword_list) - 1:
                    time.sleep(2)
            
            # Build results matrix
            status_text.text("📊 Building results matrix...")
            results_matrix = []
            
            for tcin in tcin_list:
                row = {'TCIN': tcin}
                
                for keyword in keyword_list:
                    found = False
                    for result in results_data.get(keyword, []):
                        if result['tcin'] == tcin:
                            row[keyword] = f"#{result['position']} (Page {result['page']})"
                            found = True
                            break
                    
                    if not found:
                        row[keyword] = '—'
                
                results_matrix.append(row)
            
            # Display results
            st.markdown("---")
            st.subheader("📊 Results")
            
            df = pd.DataFrame(results_matrix)
            
            # Style the dataframe
            def highlight_found(val):
                if val == '—':
                    return 'color: #999999'
                else:
                    return 'background-color: #d4edda; color: #155724; font-weight: bold'
            
            styled_df = df.style.applymap(highlight_found, subset=keyword_list)
            st.dataframe(styled_df, use_container_width=True, height=400)
            
            # Summary statistics
            st.markdown("---")
            col1, col2, col3 = st.columns(3)
            
            total_checks = len(tcin_list) * len(keyword_list)
            found_count = sum(1 for row in results_matrix for k in keyword_list if row[k] != '—')
            
            with col1:
                st.metric("Total Checks", total_checks)
            with col2:
                st.metric("Found", found_count)
            with col3:
                st.metric("Success Rate", f"{(found_count/total_checks*100):.1f}%")
            
            # Download button
            st.markdown("---")
            csv = df.to_csv(index=False)
            st.download_button(
                label="📥 Download Results as CSV",
                data=csv,
                file_name=f"target_tcin_results_{time.strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv",
                use_container_width=True
            )
            
            status_text.text("✅ Search complete!")
            
        except Exception as e:
            st.error(f"❌ An error occurred: {str(e)}")
            import traceback
            with log_container:
                st.code(traceback.format_exc())
            
        finally:
            if driver:
                try:
                    driver.quit()
                    with log_container:
                        st.write("🔒 Browser closed")
                except:
                    pass

if __name__ == "__main__":
    main()