from app.settings import settings

# creates prompts for the review, transforms PR data in review requests

# github pr data -> friendly prompt for llm
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

            # if the patch is too large, show summary w/ line count because too big for llm
            if len(patch) < 2000:
                files_summary.append(f"\n**File: {filename}**\n```diff\n{patch}\n```")
            else:
                files_summary.append(f"\n**File: {filename}** (Large file - {additions}+ {deletions}- lines)")

        # validate against configured limits in settings
        if total_changes > settings.max_changed_lines_reviewed:
            files_summary.append(f"\n⚠️ **Warning**: Total changes ({total_changes}) exceed configured limit ({settings.max_changed_lines_reviewed})")

        files_content = "\n".join(files_summary)

        prompt = f"""You are an expert software engineer performing a code review.

            Please analyze the following code changes and provide:
                1. **Security Issues**: Identify any potential security vulnerabilities
                2. **Bugs**: Spot logical errors or edge cases
                3. **Code Quality**: Suggest improvements for readability, performance, and maintainability
                4. **Best Practices**: Recommend following language/framework conventions
                5. **Testing**: Suggest areas that need test coverage

            Focus on the most critical issues first. Be specific and actionable in your feedback.

            Code Changes (Total: {total_changes} lines):
            {files_content}

            Provide your review in a clear, structured format:"""

        return prompt
