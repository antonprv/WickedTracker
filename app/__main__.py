import os
import requests
import yaml
import zipfile
import io
import shutil


def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_last_id(path):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def save_last_id(path, artifact_id):
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(artifact_id))


def get_latest_successful_run(cfg):
    url = (
        f"https://api.github.com/repos/{cfg['github']['repo']}/actions/"
        f"workflows/{cfg['github']['workflow_id']}/runs?status=success&per_page=1"
    )
    r = requests.get(url, headers={"Authorization": f"Bearer {cfg['github']['token']}"})
    r.raise_for_status()
    runs = r.json().get("workflow_runs", [])
    return runs[0] if runs else None


def get_artifacts_for_run(run, cfg):
    url = f"{run['url']}/artifacts"
    r = requests.get(url, headers={"Authorization": f"Bearer {cfg['github']['token']}"})
    r.raise_for_status()
    return r.json().get("artifacts", [])


def download_artifact(artifact, cfg):
    url = artifact["archive_download_url"]
    r = requests.get(
        url,
        headers={"Authorization": f"Bearer {cfg['github']['token']}", "Accept": "application/zip"},
    )
    r.raise_for_status()
    return io.BytesIO(r.content)


def extract_files(zip_data, cfg):
    extract_dir = cfg["output"]["extract_dir"]
    files_to_extract = cfg["artifacts"]["files_to_extract"]
    extract_mode = cfg["artifacts"]["extract_mode"]

    os.makedirs(extract_dir, exist_ok=True)

    with zipfile.ZipFile(zip_data) as z:
        for fpath in files_to_extract:
            if fpath not in z.namelist():
                continue

            target_path = os.path.join(extract_dir, os.path.basename(fpath))

            with z.open(fpath) as src, open(target_path, "wb") as dst:
                shutil.copyfileobj(src, dst)

            if extract_mode == "move":
                # place for post-processing
                pass
            elif extract_mode == "custom":
                # implement custom extraction behavior
                pass


def main():
    cfg = load_config()

    last_id_file = cfg["state"]["last_artifact_id_file"]
    last_id = load_last_id(last_id_file)

    run = get_latest_successful_run(cfg)
    if not run:
        return

    artifacts = get_artifacts_for_run(run, cfg)
    if not artifacts:
        return

    # find your target artifact by name
    target = next(
        (a for a in artifacts if a["name"] == cfg["artifacts"]["name"]),
        None
    )
    if not target:
        return

    current_id = str(target["id"])

    if current_id == last_id:
        return

    zip_data = download_artifact(target, cfg)
    extract_files(zip_data, cfg)

    save_last_id(last_id_file, current_id)


if __name__ == "__main__":
    main()

