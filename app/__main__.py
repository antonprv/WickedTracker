import os
import requests
import yaml
import zipfile
import io
import shutil
import subprocess

def load_config():
    print("loading config...")
    with open("config/config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_last_id(path):
    print("checking last id...")
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


def save_last_id(path, artifact_id):
    print("saving last id...")
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(artifact_id))


def get_latest_successful_run(cfg):
    print("getting latest successful run")
    url = (
        f"https://api.github.com/repos/{cfg['github']['repo']}/actions/"
        f"workflows/{cfg['github']['workflow_id']}/runs?status=success&per_page=1"
    )
    r = requests.get(url, headers={"Authorization": f"Bearer {cfg['github']['token']}"})
    r.raise_for_status()
    runs = r.json().get("workflow_runs", [])
    print("sucess")
    return runs[0] if runs else None


def get_artifacts_for_run(run, cfg):
    print("getting artifacts for run...")
    url = f"{run['url']}/artifacts"
    r = requests.get(url, headers={"Authorization": f"Bearer {cfg['github']['token']}"})
    r.raise_for_status()
    print("success")
    return r.json().get("artifacts", [])

def download_artifact(artifact, cfg):
    print("downloading artifact...")
    url = artifact["archive_download_url"]

    headers = {
        "Authorization": f"Bearer {cfg['github']['token']}",
        "Accept": "application/vnd.github+json"
    }

    with requests.get(url, headers=headers, stream=True) as r:
        r.raise_for_status()
        buf = io.BytesIO()

        for chunk in r.iter_content(chunk_size=1024 * 1024):  # 1 MB chunks
            if chunk:
                buf.write(chunk)

        buf.seek(0)
        print("artifact downloaded")
        return buf

def extract_files(zip_data, artifact_cfg, output_dir):
    files_to_extract = artifact_cfg.get("files_to_extract", "*")
    extract_mode = artifact_cfg.get("extract_mode", "copy")

    with zipfile.ZipFile(zip_data) as z:
        if files_to_extract == "*":
            selected = [f for f in z.namelist() if not f.endswith("/")]
        else:
            selected = [f for f in z.namelist() if f in files_to_extract]

        for fpath in selected:
            target_path = os.path.join(output_dir, fpath)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)

            with z.open(fpath) as src, open(target_path, "wb") as dst:
                shutil.copyfileobj(src, dst)

            if extract_mode == "move":
                os.remove(target_path)
            elif extract_mode == "custom":
                pass
    print("files extracted successfully")

def send_telegram_message(cfg, text):
    print("sending telegram message...")
    if not cfg["telegram"]["enabled"]:
        return

    url = f"https://api.telegram.org/bot{cfg['telegram']['bot_token']}/sendMessage"
    payload = {
        "chat_id": cfg["telegram"]["chat_id"],
        "text": text,
        "parse_mode": "HTML"
    }

    try:
        r = requests.post(url, json=payload)
        r.raise_for_status()
    except Exception as e:
        print("Failed to send telegram message:", e)

def clone_and_checkout(cfg, commit_id):
    clone_dir = cfg["output"].get("clone_dir", "./repo")
    repo_url = f"https://github.com/{cfg['github']['repo']}.git"

    if not os.path.exists(clone_dir):
        os.makedirs(clone_dir, exist_ok=True)

    print(f"Cloning repository {cfg['github']['repo']} into {clone_dir} without checkout...")
    subprocess.run(["git", "clone", "--no-checkout", repo_url, clone_dir], check=True)

    print(f"Checking out commit {commit_id}...")
    subprocess.run(["git", "-C", clone_dir, "checkout", commit_id], check=True)


def main():
    cfg = load_config()
    output_dir = cfg["output"]["extract_dir"]

    run = get_latest_successful_run(cfg)
    if not run:
        return

    artifacts = get_artifacts_for_run(run, cfg)
    if not artifacts:
        return

    last_id_file = f"{cfg['state']['last_artifact_id_file'].replace(' ', '_')}.txt"

    for artifact_cfg in cfg["artifacts"]:
        target = next(
            (a for a in artifacts if a["name"] == artifact_cfg["name"]),
            None
        )
        if not target:
            continue

        last_id = load_last_id(last_id_file)
        current_id = str(target["id"])

        if current_id == last_id:
            continue

        zip_data = download_artifact(target, cfg)
        extract_files(zip_data, artifact_cfg, output_dir)

        save_last_id(last_id_file, current_id)

    if cfg.get("telegram", {}).get("enabled"):
        commit_id = run.get("head_commit", {}).get("id", "unknown")[:7]  # короткий хэш
        commit_msg = run.get("head_commit", {}).get("message", "No commit message")
        base_msg = cfg["telegram"].get("message_on_download", f"Downloaded {artifact_cfg['name']}")
        full_msg = f"{base_msg}\nCommit: <code>{commit_id}</code>\nMessage: {commit_msg}"
        send_telegram_message(cfg, full_msg)

    commit_id = run.get("head_commit", {}).get("id", None)
    if commit_id:
        clone_and_checkout(cfg, commit_id)
        send_telegram_message(cfg, f"Received code for commit {commit_id}")

if __name__ == "__main__":
    main()
