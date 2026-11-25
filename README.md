# FFXIV Foundry VTT Modules (`Sovahless/ffxiv-foundry-modules`)

Dépôt central pour installer et mettre à jour indépendamment les modules **FFXIV x D&D 5e** sur Foundry VTT v14 (`dnd5e` v6.1.1).

Chaque module possède son propre `manifest` dans `manifests/<id>/module.json` et sa propre Release GitHub (`<id>-v<version>`) : mettre à jour un module ne force pas le retéléchargement des autres.

## Liens d'installation Foundry VTT (Manifest URL)

Dans **Modules complémentaires → Installer un module → URL du manifeste** :

| Module | Version | URL du manifeste |
|---|---|---|
| `ffxiv-dnd5e-dawntrail` | `1.1.2` | `https://raw.githubusercontent.com/Sovahless/ffxiv-foundry-modules/main/manifests/ffxiv-dnd5e-dawntrail/module.json` |
| `ffxiv-dnd5e-limit-break` | `1.0.0` | `https://raw.githubusercontent.com/Sovahless/ffxiv-foundry-modules/main/manifests/ffxiv-dnd5e-limit-break/module.json` |
| `ffxiv-dnd5e-raimdelle-bestiary` | `1.1.0` | `https://raw.githubusercontent.com/Sovahless/ffxiv-foundry-modules/main/manifests/ffxiv-dnd5e-raimdelle-bestiary/module.json` |
| `ffxiv-dnd5e-materia` | `1.0.0` | `https://raw.githubusercontent.com/Sovahless/ffxiv-foundry-modules/main/manifests/ffxiv-dnd5e-materia/module.json` |

## Publier une mise à jour depuis Windows

```powershell
# Mettre à jour un module précis (incrémente la version patch + push + GitHub Release)
python publish_github.py --module ffxiv-dnd5e-materia --bump patch --publish

# Ou re-publier tous les modules sans changer les versions
python publish_github.py --publish
```
