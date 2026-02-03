import streamlit as st
import pandas as pd
import pdfplumber
import os
import re

# --- Page Config & CSS Styling ---
st.set_page_config(layout="centered", page_title="Global Meteori Price List", initial_sidebar_state="collapsed")

st.markdown("""
<style>
    /* Global RTL direction */
    .stApp { direction: rtl; text-align: right; }
    
    /* Input alignment correction */
    .stTextInput input, .stSelectbox div, .stSelectbox span, .stNumberInput input {
        text-align: right !important; direction: rtl !important;
    }
    
    /* Sidebar alignment */
    section[data-testid="stSidebar"] { direction: rtl; text-align: right; }
    
    /* --- Product Card Styling --- */
    .product-container {
        background-color: #ffffff;
        border-radius: 16px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
        border: 1px solid #f0f0f0;
    }
    
    .product-name { 
        font-size: 18px; 
        font-weight: 600; 
        color: #1a1a1a;
        margin-bottom: 8px;
        line-height: 1.3;
    }
    
    .product-price { 
        font-size: 18px; 
        color: #2e7d32;
        font-weight: 700;
        margin-bottom: 8px;
    }
    
    /* "Add" Button Styling - Bigger Touch Targets */
    .stButton button { 
        width: 100%; 
        background-color: #007bff; 
        color: white; 
        border: none; 
        padding: 12px; 
        border-radius: 12px;
        font-size: 16px;
        font-weight: 500;
        box-shadow: 0 2px 4px rgba(0,123,255,0.2);
    }
    .stButton button:hover { 
        background-color: #0056b3; 
        color: white;
    }
    .stButton button:active {
        background-color: #004494;
    }
    
    /* Number Input Styling to match */
    .stNumberInput input {
        border-radius: 12px;
        padding: 10px;
    }

    /* CHANGE 2: Mobile Optimizations */
    /* Hide the top colored decoration bar and footer */
    header {visibility: hidden;}
    footer {visibility: hidden;}
    #MainMenu {visibility: hidden;}
    
    /* Mobile specific adjustments */
    @media only screen and (max-width: 600px) {
        .product-name { font-size: 17px; }
        .product-price { font-size: 16px; }
        .stButton button { padding: 14px; } /* Larger touch target */
        .block-container { padding-top: 1rem !important; padding-bottom: 5rem !important; }
    }

</style>
""", unsafe_allow_html=True)

#  Session State Management 
if 'cart' not in st.session_state:
    st.session_state['cart'] = []
if 'items_limit' not in st.session_state:
    st.session_state['items_limit'] = 30
if 'last_category' not in st.session_state:
    st.session_state['last_category'] = ""
if 'last_search' not in st.session_state:
    st.session_state['last_search'] = ""

#  helper functions 

def fix_hebrew(text):
    """
    Reverses Hebrew text for proper display in some PDF contexts.
    Also fixes reversed numbers using regex.
    """
    if not isinstance(text, str): return ""
    text = text.strip().replace('"', '').replace("'", "")
    
    # Return as is if no Hebrew characters
    if not any("\u0590" <= c <= "\u05FF" for c in text): return text
    
    reversed_text = text[::-1]
    
    # Fix numbers that got reversed (e.g. 5.1 -> 1.5)
    def flip_match(match): return match.group(0)[::-1]
    fixed_text = re.sub(r'\d+(?:[\.,]\d+)*', flip_match, reversed_text)
    
    return fixed_text

def get_sub_category(product_name):
    """Extracts the first word of the product name to use as a category."""
    if not isinstance(product_name, str): return "שונות"
    words = product_name.split()
    if len(words) >= 1: 
        # clean punctuation
        clean = words[0].replace("-", "").replace(".", "").replace(":", "").strip()
        if len(clean) > 1: return clean
    return "שונות"

def clean_price_value(price_str):
    """Converts price string (e.g. '35.00') to float for sorting."""
    if not isinstance(price_str, str): return 999999.0
    try:
        clean = price_str.replace('₪', '').replace(',', '').strip()
        return float(clean)
    except: return 999999.0

# data loading
@st.cache_data(show_spinner="טוען מחירון...")
def get_data():
    csv_file = 'products_final.csv'
    pdf_file = 'glob.pdf'

    # load from CSV if exists (Faster)
    if os.path.exists(csv_file):
        df = pd.read_csv(csv_file)
        if 'price_val' not in df.columns:
            df['price_val'] = df['מחיר'].apply(clean_price_value)
        return df

    # parse PDF if CSV doesn't exist
    if os.path.exists(pdf_file):
        data = []
        try:
            with pdfplumber.open(pdf_file) as pdf:
                for page in pdf.pages:
                    text = page.extract_text()
                    if not text: continue
                    for line in text.split('\n'):
                        if '₪' not in line: continue
                        parts = line.split('","')
                        clean_parts = [p.replace('"', '').strip() for p in parts]
                        
                        price = ""
                        name = ""
                        
                        # parsing logic based on CSV structure inside PDF
                        if len(clean_parts) >= 3:
                            price = clean_parts[0]
                            name = fix_hebrew(clean_parts[2])
                        elif len(clean_parts) == 2:
                            price = clean_parts[0]
                            name = fix_hebrew(clean_parts[1])
                        else:
                            match = re.match(r'(₪\s?[\d\.]+)(.*)', line)
                            if match:
                                price = match.group(1)
                                name = fix_hebrew(match.group(2))
                        
                        if "שם פריט" in name or len(name) < 2: continue
                        data.append({"שם פריט": name, "מחיר": price})

            df = pd.DataFrame(data)
            if not df.empty:
                # add calculated columns
                df['קטגוריה'] = df['שם פריט'].apply(get_sub_category)
                df['price_val'] = df['מחיר'].apply(clean_price_value)
                # save to CSV for next time
                df.to_csv(csv_file, index=False, encoding='utf-8-sig')
            return df
        except Exception as e:
            st.error(f"Error loading PDF: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

# -------------- Cart Logic (Top Action Bar) --------------
def render_cart_header():
    count = len(st.session_state['cart'])
    if count == 0:
        st.info("🛒 העגלה ריקה")
    else:
        # Create an expander for the cart
        with st.expander(f"🛒 עגלת קניות ({count} פריטים)", expanded=False):
            cart_df = pd.DataFrame(st.session_state['cart'])
            st.dataframe(cart_df[['מוצר', 'כמות', 'מחיר']], hide_index=True, use_container_width=True)
            
            # Message Generation & Copy
            msg = "*היי, הזמנה חדשה:*\n\n"
            total = 0
            for item in st.session_state['cart']:
                msg += f"🔹 {item['מוצר']} - {item['כמות']} יח'\n"
                # try to sum up if price is numeric
                try:
                    price_clean = float(str(item['מחיר']).replace('₪', '').replace(',', '').strip())
                    total += price_clean * int(item['כמות'])
                except: pass
            
            # Display Total
            st.markdown(f"<h3 style='text-align: left; color: #2e7d32;'>סה\"כ: ₪{total:,.2f}</h3>", unsafe_allow_html=True)
            msg += f"\nסה\"כ לתשלום: ₪{total:,.2f}\n"
            
            msg += "\nתודה!"
            
            st.markdown("### העתק רשימה:")
            st.code(msg, language="text")
            
            if st.button("🗑️ רוקן עגלה", key="clear_cart_top"):
                st.session_state['cart'] = []
                st.rerun()

# ------------- component: render single product row ----------------
def render_product_row(row, unique_key):
    # using container for custom styling
    container = st.container()
    
    # Custom HTML for card layout
    with container:
        col1, col2 = st.columns([2.5, 1])
        
        with col1:
            st.markdown(f"""
            <div class="product-container">
                <div class="product-name">{row['שם פריט']}</div>
                <div class="product-price">{row['מחיר']}</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col2:
            # Controls inside the card logic to align nicely
            st.write("") 
            st.write("")
            qty = st.number_input("כמות", min_value=1, value=1, key=f"q_{unique_key}", label_visibility="collapsed")
            if st.button("הוסף", key=f"btn_{unique_key}"):
                st.session_state['cart'].append({"מוצר": row['שם פריט'], "כמות": qty, "מחיר": row['מחיר']})
                st.toast(f"✅ {row['שם פריט']} נוסף!", icon="🛒")
                st.rerun()

# ------------------ main application -------------------
def main():
    render_cart_header()
    st.title("🔎 מחירון גלובל מטאורי")
    
    df = get_data()
    if df.empty: return

    # search section
    # search section
    st.subheader("🔍 חיפוש מוצר")
    
    col_search, col_sort = st.columns([3, 1])
    with col_search:
        search_query = st.text_input("הקלד שם מוצר...", "").strip()
    with col_sort:
        sort_option = st.selectbox("מיון", ["מחיר (נמוך-גבוה)", "מחיר (גבוה-נמוך)", "שם (א-ת)"], label_visibility="collapsed")
    
    # reset limit if search changes
    if search_query != st.session_state['last_search']:
        st.session_state['items_limit'] = 20
        st.session_state['last_search'] = search_query

    if search_query:
        # filter by search
        results = df[df['שם פריט'].str.contains(search_query, na=False)]
        
        # Apply Sorting
        if sort_option == "מחיר (נמוך-גבוה)":
            results = results.sort_values(by='price_val', ascending=True)
        elif sort_option == "מחיר (גבוה-נמוך)":
            results = results.sort_values(by='price_val', ascending=False)
        else:
            results = results.sort_values(by='שם פריט', ascending=True)
        
        if not results.empty:
            st.info(f"נמצאו {len(results)} תוצאות")
            limit = st.session_state['items_limit']
            
            # render items up to limit
            for i, row in results.iloc[:limit].iterrows():
                render_product_row(row, f"srch_{i}")
            
            # show "Load More" button
            if len(results) > limit:
                if st.button("⬇️ הצג עוד מוצרים"):
                    st.session_state['items_limit'] += 20
                    st.rerun()
        else:
            st.warning("לא נמצאו מוצרים.")
            
    else:
        # catalog section (no search)
        st.divider()
        st.subheader("📂 קטלוג")
        
        if 'קטגוריה' in df.columns:
            all_cats = sorted(df['קטגוריה'].unique())
            selected_cat = st.selectbox("בחר קטגוריה:", ["בחר..."] + all_cats)
            
            # reset limit if category changes
            if selected_cat != st.session_state['last_category']:
                st.session_state['items_limit'] = 20
                st.session_state['last_category'] = selected_cat

            if selected_cat and selected_cat != "בחר...":
                cat_df = df[df['קטגוריה'] == selected_cat].copy()
                
                # Apply Sorting to Category view as well
                if sort_option == "מחיר (נמוך-גבוה)":
                    cat_df = cat_df.sort_values(by='price_val', ascending=True)
                elif sort_option == "מחיר (גבוה-נמוך)":
                    cat_df = cat_df.sort_values(by='price_val', ascending=False)
                else:
                    cat_df = cat_df.sort_values(by='שם פריט', ascending=True)
                
                st.markdown(f"**מציג {len(cat_df)} מוצרים בקטגוריית {selected_cat}:**")
                st.write("") # Spacer
                
                limit = st.session_state['items_limit']
                for i, row in cat_df.iloc[:limit].iterrows():
                    render_product_row(row, f"cat_{i}")
                    
                if len(cat_df) > limit:
                    if st.button("⬇️ הצג עוד מוצרים"):
                        st.session_state['items_limit'] += 20
                        st.rerun()

if __name__ == "__main__":
    main()