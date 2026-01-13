# --- DEFENSIVE DATA ENGINE ---
@st.cache_data(ttl=3600)
def fetch_verified_data():
    api_url = "https://marsapi.ams.usda.gov/services/v1.1/reports/1831"
    try:
        response = requests.get(api_url, auth=HTTPBasicAuth('pEhHNZ2t9pmJrZ9/3ZeYI1i4gbJ5HB4Y', ''), timeout=15)
        raw_json = response.json().get('results', [])
        
        if not raw_json:
            return None, "USDA report is empty."
        
        scrubbed = []
        for r in raw_json:
            # SAFETY CHECK: Use .get() with a default value to prevent 'KeyError'
            # This is the fix for the 'frame_muscle' error
            raw_class = str(r.get('class', 'UNKNOWN')).upper()
            
            # Fuzzy match for Steers/Heifers
            if "STEER" in raw_class or "HEIFER" in raw_class:
                # Defensive Extraction: If 'frame_muscle' is missing, use 'grade' or 'N/A'
                grade = r.get('frame_muscle') or r.get('grade') or "NO GRADE"
                price = r.get('avg_price')
                weight = r.get('avg_weight')

                if price and weight:
                    scrubbed.append({
                        'sex': "Steers" if "STEER" in raw_class else "Heifers",
                        'grade': str(grade).upper(),
                        'avg_weight': float(weight),
                        'avg_price': float(price),
                        'wgt_range': r.get('wgt_range', 'N/A')
                    })
        
        if not scrubbed:
            return None, "No valid Steer/Heifer data found."
            
        return pd.DataFrame(scrubbed), "Success"
    except Exception as e:
        return None, f"System Error: {str(e)}"
