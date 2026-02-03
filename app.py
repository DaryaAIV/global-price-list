import streamlit as st
import pandas as pd
import pdfplumber
import os
import re

# --- Page Config & CSS Styling ---
st.set_page_config(layout="centered", page_title="Global Meteori Price List")

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
    
    /* Hide the top colored decoration bar of Streamlit to save space */
    header {visibility: hidden;}

    /* --- Product Card Styling (New Design) --- */
    .product-card {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        border-radius: 15px;
        padding: 15px;
        margin-bottom: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05); /* Soft shadow */
        text-align: center; /* Center everything in mobile */
    }
    
    .product-name { 
        font-size: 18px; 
        font-weight: bold; 
        color: #2c3e50; /* Dark blue-grey text */
        margin-bottom: 5px;
        min-height: 40px;
        display: flex;
        align-items: center;
        justify_content: center;
        line-height: 1.2;
    }
    
    .product-price { 
        font-size: 18px; 
        color: #2e7d32; /* Soft green for price */
        font-weight: bold;
        margin-bottom: 10px;
    }
    
    /* Button Styling */
    .stButton button { 
        width: 100%; 
        background-color: #1976d2; 
        color: white; 
        border: none; 
        padding: 0.5rem; 
        border-radius: 20px;
    }
    .stButton button:hover { background-color: #1565c0; }

</style>
""", unsafe_allow_html=True)

#  Session State Management 
if 'cart' not in st.session_state:
    st.session_state['cart'] = []
if 'items_limit' not in st.session_state:
    st.session_state['items_limit'] = 20
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
@st.cache_data
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

# -------------- sidebar logic (cart) --------------
def sidebar_logic():
    st.sidebar.title("🛒 הזמנה")
    if not st.session_state['cart']:
        st.sidebar.info("העגלה ריקה")
    else:
        st.sidebar.success(f"{len(st.session_state['cart'])} פריטים")
        cart_df = pd.DataFrame(st.session_state['cart'])
        st.sidebar.dataframe(cart_df[['מוצר', 'כמות']], hide_index=True)
        
        # generate WhatsApp message
        if st.sidebar.button("📝 צור הודעה"):
            msg = "*היי, הזמנה חדשה:*\n\n"
            for item in st.session_state['cart']:
                msg += f"🔹 {item['מוצר']} - {item['כמות']} יח'\n"
            msg += "\nתודה!"
            st.sidebar.text_area("העתק:", value=msg, height=300)
            
        # clear cart
        if st.sidebar.button("🗑️ רוקן"):
            st.session_state['cart'] = []
            st.rerun()

# ------------- component: render single product row (Card Style) ----------------
def render_product_row(row, unique_key):
    # using container for custom styling
    with st.container():
        # HTML Card display
        st.markdown(f"""
        <div class="product-card">
            <div class="product-name">{row['שם פריט']}</div>
            <div class="product-price">{row['מחיר']}</div>
        </div>
        """, unsafe_allow_html=True)
        
        # input and button below the card
        c1, c2 = st.columns([1, 2])
        
        with c1:
             qty = st.number_input("qty", min_value=1, value=1, key=f"q_{unique_key}", label_visibility="collapsed")
             
        with c2:
             if st.button("Add to Cart 🛒", key=f"btn_{unique_key}"):
                st.session_state['cart'].append({"מוצר": row['שם פריט'], "כמות": qty, "מחיר": row['מחיר']})
                st.toast(f"✅ {row['שם פריט']} נוסף!")
        
        st.write("") # small spacer

# ------------------ main application -------------------
def main():
    sidebar_logic()
    
    # Centered Title
    st.markdown("<h1 style='text-align: center;'>🔎 מחירון גלובל מטאורי</h1>", unsafe_allow_html=True)
    
    df = get_data()
    if df.empty: return

    # search section
    st.subheader("🔍 חיפוש מוצר")
    search_query = st.text_input("הקלד שם מוצר...", "").strip()
    
    # reset limit if search changes
    if search_query != st.session_state['last_search']:
        st.session_state['items_limit'] = 20
        st.session_state['last_search'] = search_query

    if search_query:
        # filter by search
        results = df[df['שם פריט'].str.contains(search_query, na=False)]
        results = results.sort_values(by='price_val', ascending=True)
        
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
                cat_df = cat_df.sort_values(by='price_val', ascending=True)
                
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