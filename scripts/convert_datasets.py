#!/usr/bin/env python3
"""
Script to convert public SZZ datasets to the validation format.

Usage:
    python convert_datasets.py defects4j datasets/defects4j-bugs.json -o datasets/defects4j_ground_truth.csv
    python convert_datasets.py icse2021 datasets/icse2021-overall.json -o datasets/icse2021_ground_truth.csv
"""
import json
import csv
import argparse
from pathlib import Path


def convert_defects4j(input_file: str, output_file: str):
    """
    Convert Defects4J Dissection JSON to validation CSV.

    Defects4J contains ONLY bug fixes (all entries are confirmed bugs).
    This dataset is useful for testing recall but NOT precision.

    To test precision, you need a dataset with both bugs AND non-bugs.
    """
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Extract project-bugId pairs (these are unique identifiers)
    # Note: Defects4J uses project-relative revision IDs, not full git hashes
    entries = []
    for bug in data:
        bug_id = bug.get('bugId')
        project = bug.get('project', 'Unknown')

        # The diff field contains the actual patch
        diff = bug.get('diff', '')

        entries.append({
            'id': f"{project}-{bug_id}",
            'project': project,
            'is_bug': True,  # All Defects4J entries are bugs
            'diff_preview': diff[:200] if diff else ''
        })

    # Write CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['id', 'project', 'is_bug', 'diff_preview'])
        writer.writeheader()
        writer.writerows(entries)

    print(f"Converted {len(entries)} Defects4J bugs to {output_file}")
    print("NOTE: Defects4J contains ONLY bugs. Useful for recall testing only.")


def convert_icse2021(input_file: str, output_file: str, include_repo: bool = True):
    """
    Convert ICSE 2021 SZZ evaluation dataset to validation CSV.

    This dataset contains:
    - fix commits (confirmed bug fixes)
    - bug-inducing commits linked to each fix

    All entries are confirmed bug fixes with developer-annotated BICs.
    """
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    entries = []
    for item in data:
        fix_commit = item.get('fix', {}).get('commit', {})
        commit_hash = fix_commit.get('hash', '')
        message = fix_commit.get('message', '')
        repo = item.get('repository', '')

        if commit_hash:
            entries.append({
                'commit_hash': commit_hash,
                'repository': repo if include_repo else '',
                'is_bug': True,  # All entries are confirmed bug fixes
                'message_preview': message[:100].replace('\n', ' ') if message else ''
            })

    # Write CSV
    fieldnames = ['commit_hash', 'repository', 'is_bug', 'message_preview'] if include_repo else ['commit_hash', 'is_bug', 'message_preview']
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(entries)

    print(f"Converted {len(entries)} ICSE 2021 fix commits to {output_file}")
    print("NOTE: This dataset contains ONLY bugs. Useful for recall testing only.")


def create_mixed_dataset(bugs_file: str, output_file: str, sample_refactoring: int = 50):
    """
    Create a mixed dataset by sampling commits.

    For proper precision/recall testing, you need both bugs AND non-bugs.
    This function creates a template that you can fill with refactoring commits.
    """
    # Load existing bugs
    with open(bugs_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        bugs = list(reader)

    # Create output with placeholders for refactoring commits
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['commit_hash', 'is_bug', 'notes'])
        writer.writeheader()

        # Write existing bugs
        for bug in bugs[:50]:  # Sample 50 bugs
            writer.writerow({
                'commit_hash': bug.get('commit_hash', bug.get('id', '')),
                'is_bug': 'true',
                'notes': 'from_dataset'
            })

        # Write placeholders for refactoring (you need to fill these manually)
        for i in range(sample_refactoring):
            writer.writerow({
                'commit_hash': f'PLACEHOLDER_REFACTORING_{i+1}',
                'is_bug': 'false',
                'notes': 'TODO: replace with actual refactoring commit hash'
            })

    print(f"Created mixed template at {output_file}")
    print(f"Contains {min(50, len(bugs))} bugs and {sample_refactoring} refactoring placeholders")
    print("Replace PLACEHOLDER_REFACTORING_* with actual refactoring commit hashes from your repo")


def extract_repos_list(input_file: str, output_file: str):
    """
    Extract unique repository URLs from ICSE 2021 dataset.
    Useful for cloning repos to run validation.
    """
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    repos = set()
    for item in data:
        repo = item.get('repository', '')
        if repo:
            repos.add(repo)

    with open(output_file, 'w', encoding='utf-8') as f:
        for repo in sorted(repos):
            f.write(f"https://github.com/{repo}\n")

    print(f"Extracted {len(repos)} unique repositories to {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Convert SZZ datasets to validation format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python convert_datasets.py defects4j ../datasets/defects4j-bugs.json -o ../datasets/defects4j.csv
    python convert_datasets.py icse2021 ../datasets/icse2021-overall.json -o ../datasets/icse2021.csv
    python convert_datasets.py repos ../datasets/icse2021-overall.json -o ../datasets/repos.txt
        """
    )

    parser.add_argument('format', choices=['defects4j', 'icse2021', 'repos', 'mixed'],
                        help='Dataset format to convert')
    parser.add_argument('input', help='Input file path')
    parser.add_argument('-o', '--output', required=True, help='Output file path')

    args = parser.parse_args()

    if args.format == 'defects4j':
        convert_defects4j(args.input, args.output)
    elif args.format == 'icse2021':
        convert_icse2021(args.input, args.output)
    elif args.format == 'repos':
        extract_repos_list(args.input, args.output)
    elif args.format == 'mixed':
        create_mixed_dataset(args.input, args.output)


if __name__ == '__main__':
    main()
