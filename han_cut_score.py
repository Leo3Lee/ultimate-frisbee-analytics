import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans

# Load the data
df = pd.read_csv("./processed/all_per_player_per_point.csv")

# Aggregate per-player stats
agg_cols = [
    'touches', 'throws', 'completions', 'assists',
    'goals', 'yards_gain_m', 'hucks', 'swings', 'dumps'
]
player_stats = df.groupby('player')[agg_cols].sum().fillna(0)

# Define handler and cutter tendency scores
player_stats['handler_score'] = (
    player_stats['throws'] +
    player_stats['completions'] +
    player_stats['assists'] +
    player_stats['swings'] +
    player_stats['dumps']
) / player_stats['touches'].replace(0, np.nan)

player_stats['cutter_score'] = (
    player_stats['goals'] +
    (player_stats['yards_gain_m'] / 10.0) +
    player_stats['hucks']
) / player_stats['touches'].replace(0, np.nan)

# Fill NaN values for players with no touches
player_stats[['handler_score', 'cutter_score']] = player_stats[['handler_score', 'cutter_score']].fillna(0)

# Prepare features for KMeans clustering
X_feat = player_stats[['handler_score', 'cutter_score']].values

# Fit KMeans with 3 clusters: Primary Handler, Hybrid, Primary Cutter
kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
clusters = kmeans.fit_predict(X_feat)
player_stats['cluster'] = clusters

# Label clusters based on centroid positions
centroids = kmeans.cluster_centers_
cluster_labels = {}
for i, (h_score, c_score) in enumerate(centroids):
    if h_score > c_score and h_score > 0.5:
        cluster_labels[i] = "Primary Handler"
    elif c_score > h_score and c_score > 0.5:
        cluster_labels[i] = "Primary Cutter"
    else:
        cluster_labels[i] = "Hybrid"

player_stats['role_label'] = player_stats['cluster'].map(cluster_labels)

# Plot
plt.figure(figsize=(8, 6))
role_colors = {
    "Primary Handler": "red",
    "Hybrid": "blue",
    "Primary Cutter": "green"
}

for role, subset in player_stats.groupby('role_label'):
    plt.scatter(
        subset['handler_score'],
        subset['cutter_score'],
        color=role_colors[role],
        label=role,
        s=100,
        alpha=0.7
    )
    for name, row in subset.iterrows():
        plt.text(
            row['handler_score'] + 0.01,
            row['cutter_score'] + 0.01,
            name,
            fontsize=8
        )

plt.xlabel("Handler tendency (per touch)")
plt.ylabel("Cutter tendency (per touch)")
plt.title("Handler vs Cutter Tendencies (K-Means Clustering with Roles)")
plt.legend()
plt.grid(True)

# Save plot
plot_labeled_path = "./processed/handler_vs_cutter_kmeans_labeled.png"
plt.savefig(plot_labeled_path, dpi=300, bbox_inches='tight')
plt.close()