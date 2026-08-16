# Duration de liquidité

Ce projet étudie la liquidité d'un portefeuille synthétique via un modèle de coût de cession et une mesure de duration de liquidité.

## Objectif

Le notebook et le script Python calculent :

- le coût de cession d'un portefeuille selon l'horizon de liquidation,
- le besoin net de liquidité par scénario,
- la surface horizon × scénario,
- la duration de liquidité par différence finie centrée,
- les figures associées à l'analyse de liquidité.

## Fichiers principaux

- `liquidity_duration.ipynb` : version exploitable dans Jupyter / VS Code Notebook.
- `liquidity_duration.py` : version script Python équivalente.
- `calibration.csv` : paramètres de calibration microstructure.
- `portefeuille.csv` : composition du portefeuille.
- `surface_horizon_scenario.csv` : résultats de la surface horizon/scénario.
- `duration_totale.csv` : duration de liquidité totale.
- `duration_directe.csv` : effet direct du marché.
- `duration_volume.csv` : effet volume (rachats).

## Prérequis

Installez les dépendances Python suivantes :

```bash
pip install numpy pandas matplotlib jupyter
```

## Utilisation

### Avec Jupyter / VS Code

Ouvrez le notebook :

```bash
jupyter notebook liquidity_duration.ipynb
```

ou ouvrez directement le fichier dans VS Code et lancez les cellules.

Le script génère les fichiers CSV et les images dans le même dossier.

## Sorties produites

Les figures générées sont :

- `fig_cout_par_classe.png`
- `fig_surface_scenarios.png`
- `fig_duration_decomposition.png`
- `fig_heatmap_surface.png`

## Notes

Ce travail repose sur des hypothèses de calibration microstructure et sert à illustrer un cadre méthodologique de liquidité de portefeuille, plutôt qu'à fournir une estimation de marché directe.
