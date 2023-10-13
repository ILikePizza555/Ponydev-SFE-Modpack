import requests
import pandas as pd
import logging
from dataclasses import dataclass
from typing import List, Optional
from tomlkit import document, table, inline_table, dump

logging.basicConfig(level=logging.INFO)

# Load the data from the CSV
df_mods = pd.read_csv("Ponydevs Modpack.csv", header=None)
df_mods.columns = ['Mod Name', 'Version', 'Type', 'URL', 'Status', 'Description']

# Filter out removed mods
df_mods = df_mods[df_mods['Status'] != 'REMOVED']

# Filter out custom mods
df_mods = df_mods[df_mods['URL'] != 'Custom Jar']

BASE_URL = "https://api.modrinth.com/v2"

HEADERS = {
    "User-Agent": "github.com/ILikePizza555/Ponydev-SFE-Modpack"
}


@dataclass
class ProjectModel:
    slug: str
    title: str
    description: str
    categories: List[str]
    client_side: str  # Enum: "required", "optional", "unsupported"
    server_side: str  # Enum: "required", "optional", "unsupported"
    body: str
    status: str  # Enum values provided in the documentation
    project_type: str  # Enum: "mod", "modpack", "resourcepack", "shader"
    downloads: int
    id: str
    team: str
    published: str  # ISO-8601 format
    updated: str  # ISO-8601 format
    followers: int
    versions: List[str]
    game_versions: List[str]
    loaders: List[str]
    
    # Optional fields
    requested_status: Optional[str] = None
    additional_categories: Optional[List[str]] = None
    issues_url: Optional[str] = None
    source_url: Optional[str] = None
    wiki_url: Optional[str] = None
    discord_url: Optional[str] = None
    icon_url: Optional[str] = None
    color: Optional[int] = None
    thread_id: Optional[str] = None
    monetization_status: Optional[str] = None
    body_url: Optional[str] = None  # Deprecated
    approved: Optional[str] = None  # ISO-8601 format
    queued: Optional[str] = None  # ISO-8601 format
    
    # Fields that have more complex types (like lists of objects or other dataclasses) 
    # are represented as lists for now. You can define additional dataclasses for these 
    # structures and update the type hints accordingly.
    donation_urls: List[object] = None
    moderator_message: Optional[object] = None  # Deprecated
    license: object = None
    gallery: Optional[List[object]] = None


@dataclass
class VersionModel:
    name: str
    version_number: str
    game_versions: List[str]
    version_type: str  # Enum: "release", "beta", "alpha"
    loaders: List[str]
    featured: bool
    id: str
    project_id: str
    author_id: str
    date_published: str  # ISO-8601 format
    downloads: int
    files: List[object]

    # Optional fields
    changelog: Optional[str] = None
    dependencies: List[object] = None  # Placeholder for VersionDependency
    status: Optional[str] = None  # Enum: "listed", "archived", "draft", "unlisted", "scheduled", "unknown"
    requested_status: Optional[str] = None  # Enum: "listed", "archived", "draft", "unlisted"
    changelog_url: Optional[str] = None  # Deprecated


def modrinth_api_request(endpoint: str, params: dict | None = None):
    response = requests.get(f'{BASE_URL}{endpoint}', params=params, headers=HEADERS)
    
    if not response.ok:
        error_data = response
        logging.error('Error requesting %s: %s', endpoint, response.content)
        return None
    
    return response.json()
    
def get_project(slug_or_id):
    data = modrinth_api_request(f"/project/{slug_or_id}")

    if data:
        project = ProjectModel(**data)
        logging.info('Using "%s" for mod "%s"', project.id, slug_or_id)
        return project
    
    return None

def get_version_id(mod_id, version_name):
    params = {
        "game_versions": '["1.20.1"]',
        "loaders": '["fabric"]'
    }
    data = modrinth_api_request(f"/project/{mod_id}/version", params)

    if data:
        # If version name is not none
        if version_name:
            matching_version = next((VersionModel(**v) for v in data if v['version_number'] == version_name), None)
            if matching_version:
                logging.info('Found id "%s" for version name "%s" and project_id "%s"', matching_version.id, version_name, mod_id)
                return matching_version

            logging.warning('Could not find version number "%s" for project_id "%s"', version_name, mod_id)
        else:
            logging.info('No version provided for project_id %s.', mod_id)
        
        default_version = VersionModel(**data[0])
        logging.info('Using default version "%s" (%s) for project_id %s', default_version.id, default_version.version_number, mod_id)
        return default_version
    return None


modrinth_table = table()

for _, row in df_mods.iterrows():
    mod_name = row['Mod Name']
    version_name = row['Version']
    url = row['URL']
    
    if pd.isna(url):
        logging.warning("No url for mod %s, skipping...", mod_name)

    slug = url.split('/')[-1]
    mod = get_project(slug)
    if mod is None:
        logging.error("No mod found for mod %s", mod_name)
        continue

    version = get_version_id(mod.id, version_name)
    if version is None:
        logging.error("No mod found for row %s", mod_name)
        continue

    mod_table = inline_table()
    mod_table["project"] = mod.id
    mod_table["version"] = version.id
    mod_table.comment(f"{mod.title} {version.version_number} - https://modrinth.com/mod/{mod.slug}")

    modrinth_table[mod.slug] = mod_table


output = document()
output["modrinth"] = modrinth_table

# Write to TOML
with open("mods.toml", "w", encoding="utf-8") as file:
    dump(output, file, sort_keys=True)

print("TOML file has been generated as mods.toml")