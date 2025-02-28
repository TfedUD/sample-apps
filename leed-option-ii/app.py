import zipfile
import pathlib
import json

import streamlit as st
import pandas as pd

from requests.exceptions import HTTPError
from pollination_streamlit.selectors import run_selector

from streamlit_vtkjs import st_vtkjs

from load_model import get_model_with_results
from vtk_config import leed_config


st.set_page_config(
    page_title='LEED Option II', layout='wide',
    page_icon='https://app.pollination.cloud/favicon.ico'
)

# branding, api-key and url
st.sidebar.image(
    'https://uploads-ssl.webflow.com/6035339e9bb6445b8e5f77d7/616da00b76225ec0e4d975ba_pollination_brandmark-p-500.png',
    use_column_width=True
)

api_key = st.sidebar.text_input(
    'Enter Pollination APIKEY', type='password',
    help=':bulb: You only need an API Key to access private projects. '
    'If you do not have a key already go to the settings tab under your profile to '
    'generate one.'
) or None

query_params = st.experimental_get_query_params()
defult_url = query_params['url'][0] if 'url' in query_params else \
    'https://app.pollination.cloud/projects/chriswmackey/demo/jobs/0cd8f29b-71e1-44be-9ce2-7d4c6e4e5d13/runs/ec6bbd7e-1579-550c-9e89-2ba424cd2d04'


def download_folder(run, output_name, folder):
    results_zip = run.download_zipped_output(output_name)
    with zipfile.ZipFile(results_zip) as zip_folder:
        zip_folder.extractall(folder.as_posix())

@st.cache(show_spinner=False)
def download_files(run):

    job = run.job
    results_folder = pathlib.Path('data', job.id, run.id)
    df = job.runs_dataframe.dataframe
    _, info = next(df.iterrows())
    metrics = [
        'illuminance-9am', 'illuminance-3pm', 'pass-fail-9am', 'pass-fail-3pm',
        'pass-fail-combined'
    ]

    for metric in metrics:
        download_folder(run, metric, results_folder.joinpath(metric))

    credits = results_folder.joinpath('credit_summary.json')
    data = json.load(job.download_artifact(info['credit-summary']))
    credits.write_text(json.dumps(data))

    space_summary = results_folder.joinpath('space_summary.csv')
    data = job.download_artifact(info['space-summary'])
    space_summary.write_bytes(data.read())

    # write configs to load the results
    viz_file = results_folder.joinpath('model.vtkjs')
    cfg_file = leed_config(results_folder)
    model_dict = json.load(job.download_artifact(info.model))
    get_model_with_results(
        model_dict, viz_file, cfg_file, display_mode='wireframe'
    )

    return viz_file, credits, space_summary


## get the run id
_, run_url, _ =  st.columns([0.5, 3.5, 0.5])
with run_url:
    st.header(
        'LEED Option II report'
    )

    run = run_selector(
        api_key=api_key,
        default=defult_url,
        help='See the factsheet about the results of the LEED Option II simulation.'
    )

## download related results
if run is not None:
    try:
        with st.spinner('Downloading file...'):
            viz_file, credits, space_summary = download_files(run)
    except HTTPError as e:
        with run_url:
            st.error(
                'The app cannot access this run on Pollination. Ensure the url is '
                'correct. In case the run is from a private project you will need to '
                'provide an API key to the app.\n\n :point_left: See the sidebar for '
                'more information.'
            )
        st.stop()

    recipe_info = run.recipe
    if f"{run.recipe.owner}/{run.recipe.name}" != 'pollination/leed-daylight-illuminance':
        with run_url:
            st.error(
                'This app is designed to work with pollination/leed-daylight-illuminance '
                f"recipe. The input run is using {run.recipe.owner}/{run.recipe.name}"
            )
        st.stop()
    tag_number = sum(10**c * int(i) for c, i in enumerate(recipe_info.tag.split('.')))

    if tag_number < 30:
        with run_url:
            st.error(
                'Only versions pollination/leed-daylight-illuminance:0.3.0 or higher '
                f"are valied. Current version of the recipe:{run.recipe.tag}"
            )
        st.stop()

    _, viz_c, _, info_c, _ = st.columns([0.5, 2, 0.25, 1.25, 0.5])
    with viz_c:
        st_vtkjs(viz_file.read_bytes())

    with info_c:
        data = json.loads(credits.read_text())
        points = data['credits']
        if points > 1:
            color = 'Green'
        else:
            color = 'Gray'
        credit_text = f'<h2 style="color:{color};">LEED Credits: {points} points</h2>'
        st.markdown(credit_text, unsafe_allow_html=True)
        st.markdown(f'### Percentage passing: {round(data["percentage_passing"], 2)}%')
        with st.expander('See model breakdown'):
            if points > 1:
                st.balloons()
            df = pd.DataFrame.from_dict(data, orient='index', columns=['values'])
            st.table(df.style.set_precision(1))
        with st.expander('Learn more about using the 3D viewer'):
            st.markdown(
                ' 1. Click on the ☰ icon to see the layers.\n\n'
                ' 2. Select the `Grid` layer and then select `Data`.\n\n'
                ' 3. Use the Color by dropdown to see the results for hourly '
                'illuminace or pass/fail for 9am and 3pm.'
            )

    # this is not good practice for creating the layout
    # but good enough for now
    _, table_column, _ =  st.columns([0.5, 3.5, 0.5])
    with table_column:
        st.header('Space by space breakdown')
        df = pd.read_csv(space_summary.as_posix())
        st.table(df.style.set_precision(1))
