"""Small background indexing module used by retrieval evaluation."""


def enqueue_repository_index(repo_url, queue):
    """Put a repository indexing job on the background queue."""
    queue.put({"action": "index", "repo_url": repo_url})


def retry_failed_job(job, queue):
    """Requeue an indexing job that failed."""
    job["attempts"] += 1
    queue.put(job)


def find_python_sources(root, walker):
    """Return the Python source files found beneath a folder."""
    return walker(root, suffix=".py")
