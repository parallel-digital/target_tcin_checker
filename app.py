"""
Target TCIN Indexing Checker - Streamlit App
A web-based tool for checking if TCINs appear in Target.com search results

Installation:
pip install streamlit selenium webdriver-manager pandas beautifulsoup4

Run:
streamlit run app.py

Deploy to Streamlit Cloud:
1. Push this file to GitHub
2. Go to share.streamlit.io
3. Connect your repo and deploy
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
from webdriver_manager.chrome import ChromeDriverManager
import io

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
    """Initialize Selenium WebDriver"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
    
    try:
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        return driver
    except Exception as e:
        st.error(f"Error initializing browser: {str(e)}")
        return None

def search_target_keyword(driver, keyword, max_pages, progress_bar, status_text):
    """Search Target for a keyword and extract TCINs"""
    all_tcins = []
    
    for page in range(1, max_pages + 1):
        try:
            offset = (page - 1) * 24
            url = f"https://www.target.com/s?searchTerm={keyword}&Nao={offset}"
            
            status_text.text(f"🔍 Searching '{keyword}' - Page {page}/{max_pages}...")
            driver.get(url)
            
            # Wait for products to load
            wait = WebDriverWait(driver, 15)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-test="product-card"], a[href*="/p/"]')))
            time.sleep(2)
            
            # Extract TCINs
            page_html = driver.page_source
            tcin_pattern = r'/p/[^/]+/-/A-(\d+)'
            found_tcins = re.findall(tcin_pattern, page_html)
            
            # Remove duplicates while preserving order
            unique_tcins = list(dict.fromkeys(found_tcins))
            
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
            
            # Stop if fewer products than expected
            if len(unique_tcins) < 24:
                break
                
            time.sleep(1.5)
            
        except Exception as e:
            st.warning(f"⚠️ Error on page {page} for '{keyword}': {str(e)}")
            break
    
    return all_tcins

def main():
    # Header
    st.title("🎯 Target TCIN Indexing Checker")
    st.markdown("**Check if your TCINs appear in Target.com search results across multiple keywords and pages**")
    
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
            driver = init_driver()
            
            if not driver:
                st.error("Failed to initialize browser. Please try again.")
                return
            
            # Search each keyword
            for idx, keyword in enumerate(keyword_list):
                with log_container:
                    st.write(f"\n**Searching: {keyword}**")
                
                page_progress = st.progress(0)
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
            
        finally:
            if driver:
                driver.quit()
                with log_container:
                    st.write("🔒 Browser closed")

if __name__ == "__main__":
    main()