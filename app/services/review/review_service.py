class ReviewService:
    def create_review_prompt(self, pr_details: dict, changed_files: list) -> str:
        files_summary = []
        total_changes = 0

        for file in changed_files:
            filename = file['filename']
            additions = file.get('additions', 0)
            deletions = file.get('deletions', 0)
            total_changes += additions + deletions

            patch = file.get('patch', '')
            if len(patch) < 2000:
                files_summary.append(f"\n**File: {filename}**\n```diff\n{patch}\n```")
            else:
                files_summary.append(f"\n**File: {filename}** (Large file - {additions}+ {deletions}- lines)")

        files_content = "\n".join(files_summary)

        prompt = f"""You are an expert code reviewer...
{files_content}
"""
        return prompt
