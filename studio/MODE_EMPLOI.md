# Fabric Ops Studio — description et mode d'emploi

Fabric Ops Studio est une console locale Windows pour explorer Microsoft Fabric.
Elle utilise les outils du Fabric Toolbox et présente les opérations, leur source,
leurs paramètres et leurs résultats dans une interface web.

La version **0.8.0-rc.1** est une préversion en lecture seule : inventaire des
workspaces, accès, capacités et connexions ; consultation des items, exécutions,
planifications et état Git ; export JSON/CSV ; diagnostics et historique.
Les créations, modifications et suppressions sont désactivées. Security Audit,
Assessment et Lineage présentent les outils existants et leurs prérequis ; leur
exécution intégrée n'est pas disponible dans cette version.

## Prérequis

Utiliser **PowerShell 7**, **Python 3.13**, **Node.js 22.12 ou supérieur dans la
branche 22**, et **npm 10 ou 11**, disponibles dans le PATH. Git est nécessaire
pour cloner le dépôt ; une archive de la release convient également.

```powershell
pwsh --version
python --version
node --version
npm --version
```

Le module MicrosoftFabricMgmt fourni dans le dépôt nécessite également ces
modules PowerShell. Dans PowerShell 7, les installer pour l'utilisateur courant
si nécessaire :

```powershell
Install-Module PSFramework -MinimumVersion 1.12.345 -Scope CurrentUser
Install-Module Az.Accounts -MinimumVersion 5.0.0 -Scope CurrentUser
Install-Module Az.Resources -MinimumVersion 6.15.1 -Scope CurrentUser
Install-Module MicrosoftPowerBIMgmt -MinimumVersion 1.2.1111 -Scope CurrentUser
```

La connexion nécessite un compte autorisé à consulter les ressources du tenant.
Les résultats dépendent des droits de ce compte.

## Installation et démarrage

Pour utiliser la candidate publiée et figée :

```powershell
git clone --branch studio-v0.8.0-rc.1 https://github.com/julian-passebecq/fabric-toolbox_J.git
Set-Location fabric-toolbox_J
.\studio\scripts\start-studio.ps1
```

Pour suivre la version intégrée à `main`, cloner sans `--branch`, ou utiliser
`git switch main` puis `git pull --ff-only` dans un clone existant sans changements
locaux en attente.

Le premier lancement installe les dépendances Python et npm verrouillées, démarre
les deux services locaux et ouvre **http://127.0.0.1:5173**. Garder le lanceur
ouvert pendant l'utilisation. **Ctrl+C** arrête les processus qu'il a créés.
Le runtime supporté exige le dépôt complet : il n'y a pas d'installateur autonome.

Options utiles depuis la racine du dépôt :

```powershell
.\studio\scripts\start-studio.ps1 -NoBrowser
.\studio\scripts\start-studio.ps1 -SkipInstall
.\studio\scripts\start-studio.ps1 -PythonPath 'C:\Python313\python.exe'
.\studio\scripts\start-studio.ps1 -ApiPort 28765 -UiPort 25173
```

`-SkipInstall` réutilise les dépendances après un premier lancement réussi.
Avec les ports alternatifs ci-dessus, ouvrir **http://127.0.0.1:25173**.

## Utilisation

1. Saisir l'identifiant du tenant dans **Tenant**, puis cliquer sur **Connect** et
   terminer l'authentification Microsoft.
2. Ouvrir **Workspaces**, cliquer sur **Refresh**, puis sur **Use workspace**.
3. Ouvrir **Items** et sélectionner **Use item**. Le changement de workspace
   efface l'item précédemment sélectionné.
4. Consulter les détails, connexions, runs, schedules ou l'état Git. Les paramètres
   de contexte sont renseignés automatiquement ; compléter les champs obligatoires
   restants avant d'exécuter une lecture autorisée.
5. Examiner le résultat sous forme de tableau ou JSON et utiliser les exports
   **JSON** ou **CSV** selon le besoin.
6. Consulter **Diagnostics**, **Activity Log** et **Sources** pour vérifier
   l'environnement, l'historique et la provenance des opérations.

Une opération visible dans le catalogue peut être bloquée : seules les dix
lectures explicitement admises peuvent s'exécuter. Les pages **Change Plans** et
les opérations d'écriture n'autorisent aucune modification de Fabric dans cette
release.

## Dépannage

- **Port occupé** : choisir des ports libres avec `-ApiPort` et `-UiPort`.
- **Mauvaise version Python ou Node** : vérifier le PATH ; utiliser `-PythonPath`
  pour sélectionner Python 3.13.
- **SkipInstall refusé** : relancer sans cette option après une modification des
  dépendances ou un changement de version.
- **Échec d'import du fournisseur** : vérifier les modules PowerShell ci-dessus
  et le module fourni sous `tools/MicrosoftFabricMgmt/output/module`.
- **Session perdue** : se reconnecter au tenant avant de relancer une lecture.
- **Échec du lancement** : consulter les journaux dans `studio/.run` et les
  détails affichés par le lanceur.

## Validation

La [CI Windows/Linux](https://github.com/julian-passebecq/fabric-toolbox_J/actions/runs/37252347044)
a validé le candidat publié : 145 tests backend, 17 tests composants, build et
4 tests navigateur par plateforme, plus les contrôles du lanceur Windows.
Les tests utilisent des fixtures ; aucune connexion ni lecture sur un tenant réel
n'a été réalisée pour cette release.

Voir le [README technique](README.md) et la
[release publiée](https://github.com/julian-passebecq/fabric-toolbox_J/releases/tag/studio-v0.8.0-rc.1).
