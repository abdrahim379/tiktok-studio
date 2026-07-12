import streamlit as st
import subprocess
import sys
import os

st.set_page_config(
    page_title="All Ecom Apps Launcher",
    page_icon="🚀",
    layout="centered"
)

st.title("🚀 All Ecom Apps Launcher")
st.markdown("### Select the app you want to run")

# ---- App Selection ----
app_choice = st.selectbox(
    "Choose an app:",
    [
        "Snapchat Ad Variant Generator",
        "TikTok Variant Generator",
        "TikTok Downloader"
    ]
)

st.markdown("---")

def run_app(filename):
    """Launch selected Streamlit or Flask app"""
    try:
        if filename.endswith(".py"):
            # Open new terminal window and run app
            if sys.platform == "win32":
                subprocess.Popen(f'start cmd /k streamlit run {filename}', shell=True)
            elif sys.platform == "darwin":  # macOS
                subprocess.Popen(["open", "-a", "Terminal", f"streamlit run {filename}"])
            else:  # Linux
                subprocess.Popen(["gnome-terminal", "--", "streamlit", "run", filename])

        st.success(f"✅ {filename} launched successfully!")

    except Exception as e:
        st.error(f"❌ Failed to launch app: {e}")

# ---- Launch Button ----
if st.button("🚀 Launch Selected App"):

    if app_choice == "Snapchat Ad Variant Generator":
        run_app("snapchat_variants.py")

    elif app_choice == "TikTok Variant Generator":
        run_app("tiktok_4variants.py")

    elif app_choice == "TikTok Downloader":
        # This one is Flask, not Streamlit
        try:
            if sys.platform == "win32":
                subprocess.Popen("start cmd /k python tiktok_downloaderCNX.py", shell=True)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", "-a", "Terminal", "python tiktok_downloaderCNX.py"])
            else:
                subprocess.Popen(["gnome-terminal", "--", "python", "tiktok_downloaderCNX.py"])

            st.success("✅ TikTok Downloader launched!")
        except Exception as e:
            st.error(f"❌ Failed to launch downloader: {e}")

st.markdown("---")
st.info("Make sure all app files are in the same folder as allecomapp.py")
