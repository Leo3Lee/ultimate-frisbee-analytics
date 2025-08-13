# Ultimate Frisbee Analytics Project

A comprehensive analytics project for Ultimate Frisbee game data, featuring interactive network visualizations and player chemistry analysis.

## Features

### 🥏 Interactive Network Visualization
- **Player Chemistry Analysis**: Interactive D3.js network showing pass completion relationships
- **Multi-Player Selection**: Select specific players to analyze their chemistry
- **Mode Switching**: View All/Throws/Receptions patterns
- **Real-time Filtering**: Filter by minimum completions and hide isolated nodes
- **Enhanced Hover Effects**: Dynamic emphasis based on selection and mode

### 📊 Data Processing
- **Multi-Game Analysis**: Combines data from 6 different games
- **Player Role Classification**: K-means clustering to identify handlers vs cutters
- **Statistical Aggregation**: Per-player and per-point statistics
- **Pass Completion Tracking**: Detailed analysis of throwing and receiving patterns

## Files

### Core Scripts
- `completion.py` - Interactive network visualization generator
- `han_cut_score.py` - Handler/cutter role classification
- `batch_ingest_statto.py` - Data ingestion and processing
- `statto_bridge.py` - Data bridging utilities
- `vis.py` - Additional visualization scripts

### Data Structure
```
data/
├── [Team Name]/
│   ├── Passes vs. [Team] [Date].csv
│   ├── Player Stats vs. [Team] [Date].csv
│   ├── Points vs. [Team] [Date].csv
│   └── ...
processed/
├── all_completions_network.html  # Interactive visualization
├── all_per_player_per_point.csv
├── all_point_level_summary.csv
└── ...
```

## Usage

1. **Run the interactive visualization**:
   ```bash
   python completion.py
   ```
   Then open `processed/all_completions_network.html` in your web browser.

2. **Generate role classifications**:
   ```bash
   python han_cut_score.py
   ```

## Requirements

- Python 3.8+
- pandas
- numpy
- matplotlib
- scikit-learn
- D3.js (loaded via CDN in HTML)

## Interactive Features

The network visualization includes:
- **Drag nodes** to reposition players
- **Multi-select players** to focus on specific chemistry
- **Mode switching** (All/Throws/Receptions)
- **Minimum completion filtering**
- **Hide isolated nodes** option
- **Real-time statistics** display
- **Enhanced hover emphasis** based on selections

## Data Sources

Game data from multiple Ultimate Frisbee matches including:
- Blok Choy
- Cookie Cutters  
- Disc Diva
- Flat Ballers Association
- Mild Threat
- Star

## License

[Add your license here]
