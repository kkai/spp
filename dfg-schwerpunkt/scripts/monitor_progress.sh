#!/bin/bash
# Monitor scraping progress

echo "=== DFG Project Scraper Progress Monitor ==="
echo ""

while true; do
    clear
    echo "=== DFG Project Scraper Progress Monitor ==="
    echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""

    # Count completed SPP files
    completed=$(ls data/raw/projects/*.json 2>/dev/null | wc -l | tr -d ' ')
    total=20

    echo "Progress: $completed / $total SPP programs scraped"
    echo ""

    # Show latest files
    echo "Latest scraped programs:"
    ls -lt data/raw/projects/*.json 2>/dev/null | head -5 | awk '{print $9}' | xargs -I {} basename {}
    echo ""

    # Count total projects
    total_projects=0
    for f in data/raw/projects/*.json; do
        if [ -f "$f" ]; then
            count=$(python3 -c "import json; print(json.load(open('$f')).get('projects_count', 0))" 2>/dev/null)
            total_projects=$((total_projects + count))
        fi
    done

    echo "Total projects collected: $total_projects"
    echo ""

    # Check if scraper is still running
    if pgrep -f "scrape_projects.py" > /dev/null; then
        echo "Status: ✓ Scraper is running"
        echo ""
        echo "Press Ctrl+C to stop monitoring (scraper will continue)"
        sleep 10
    else
        echo "Status: ✗ Scraper has stopped"
        echo ""
        if [ "$completed" -eq "$total" ]; then
            echo "🎉 All SPP programs scraped successfully!"
        else
            echo "⚠️  Scraping incomplete. Check logs for errors."
        fi
        break
    fi
done
