"""
CodeCraftHub - Course Tracking REST API

This Flask application provides CRUD operations for courses:

POST   /api/courses       Create a course
GET    /api/courses       Get all courses
GET    /api/courses/stats Get course statistics
GET    /api/courses/<id>  Get one course
PUT    /api/courses/<id>  Update one course
DELETE /api/courses/<id>  Delete one course

Course data is stored in a simple JSON file instead of a database.
"""

import json
from datetime import date, datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, request


# -----------------------------------------------------------------------------
# Flask application setup
# -----------------------------------------------------------------------------

app = Flask(__name__)

# Store courses.json in the same directory as this app.py file.
DATA_FILE = Path(__file__).parent / "courses.json"

# These are the only status values accepted by the API.
VALID_STATUSES = {
    "Not Started",
    "In Progress",
    "Completed",
}


# -----------------------------------------------------------------------------
# JSON file helper functions
# -----------------------------------------------------------------------------

def create_data_file_if_missing():
    """
    Create courses.json automatically if it does not already exist.

    The file starts with an empty JSON array because there are no courses yet.
    """
    if not DATA_FILE.exists():
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as file:
                json.dump([], file, indent=4)
        except OSError as error:
            raise OSError(
                f"Could not create data file: {error}"
            ) from error


def read_courses():
    """
    Read and return all courses from courses.json.

    Returns:
        list: A list of course dictionaries.

    Raises:
        OSError: If the file cannot be created or read.
        json.JSONDecodeError: If the JSON file contains invalid JSON.
        ValueError: If the JSON content is not a list.
    """
    create_data_file_if_missing()

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as file:
            courses = json.load(file)
    except OSError as error:
        raise OSError(
            f"Could not read courses.json: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise ValueError(
            f"courses.json contains invalid JSON: {error}"
        ) from error

    # The application expects the file to contain a JSON array.
    if not isinstance(courses, list):
        raise ValueError("courses.json must contain a JSON array")

    return courses


def write_courses(courses):
    """
    Write the supplied list of courses to courses.json.

    Args:
        courses (list): The courses to save.

    Raises:
        OSError: If the file cannot be written.
    """
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as file:
            json.dump(courses, file, indent=4)
    except OSError as error:
        raise OSError(
            f"Could not write to courses.json: {error}"
        ) from error


# -----------------------------------------------------------------------------
# Validation and utility functions
# -----------------------------------------------------------------------------

def get_next_course_id(courses):
    """
    Generate the next numeric course ID.

    IDs start at 1. If there are no courses, the first ID is 1.
    Otherwise, the next ID is one greater than the largest existing ID.
    """
    if not courses:
        return 1

    existing_ids = [
        course.get("id", 0)
        for course in courses
        if isinstance(course.get("id", 0), int)
    ]

    if not existing_ids:
        return 1

    return max(existing_ids) + 1


def validate_course_data(data, partial=False):
    """
    Validate fields supplied when creating or updating a course.

    All four course fields are required when creating a course:
    - name
    - description
    - target_date
    - status

    When partial=True (updates), only the supplied fields are validated,
    but at least one of them must be present.

    Returns:
        str or None: An error message, or None if the data is valid.
    """
    if not isinstance(data, dict):
        return "Request body must be a JSON object"

    required_fields = [
        "name",
        "description",
        "target_date",
        "status",
    ]

    if partial and not any(field in data for field in required_fields):
        return (
            "Request body must include at least one of: "
            + ", ".join(required_fields)
        )

    # Check that every required field exists and has a useful value.
    missing_fields = []

    for field in required_fields:
        if partial and field not in data:
            continue

        value = data.get(field)

        if value is None:
            missing_fields.append(field)
        elif isinstance(value, str) and not value.strip():
            missing_fields.append(field)

    if missing_fields:
        return (
            "Missing required fields: "
            + ", ".join(missing_fields)
        )

    # Validate the course status.
    if "status" in data and data["status"] not in VALID_STATUSES:
        return (
            "Invalid status. Status must be one of: "
            "'Not Started', 'In Progress', or 'Completed'"
        )

    # Validate the target date using the YYYY-MM-DD format.
    if "target_date" in data:
        try:
            date.fromisoformat(data["target_date"])
        except (TypeError, ValueError):
            return "target_date must use the YYYY-MM-DD format"

    return None


def get_json_request_body():
    """
    Get the JSON request body.

    Returns:
        tuple: (data, error_message)

    This helper lets the API return a friendly error when the client sends
    invalid JSON or does not send a JSON object.
    """
    if not request.is_json:
        return None, "Request must use Content-Type: application/json"

    data = request.get_json(silent=True)

    if data is None:
        return None, "Request body contains invalid JSON"

    if not isinstance(data, dict):
        return None, "Request body must be a JSON object"

    return data, None


def find_course(courses, course_id):
    """
    Find a course by its numeric ID.

    Returns:
        dict or None: The matching course, if found.
    """
    for course in courses:
        if course.get("id") == course_id:
            return course

    return None


def current_timestamp():
    """
    Return the current UTC time as an ISO 8601 timestamp.

    Example:
        2026-10-30T12:45:10.123456+00:00
    """
    return datetime.now(timezone.utc).isoformat()


# -----------------------------------------------------------------------------
# Error handlers
# -----------------------------------------------------------------------------

@app.errorhandler(404)
def handle_404(error):
    """Return JSON instead of Flask's default HTML 404 page."""
    return jsonify({
        "error": "The requested endpoint was not found"
    }), 404


@app.errorhandler(405)
def handle_405(error):
    """Return JSON when an HTTP method is not supported."""
    return jsonify({
        "error": "HTTP method is not allowed for this endpoint"
    }), 405


# -----------------------------------------------------------------------------
# Course API routes
# -----------------------------------------------------------------------------

@app.route("/api/courses", methods=["POST"])
@app.route("/api/courses/", methods=["POST"])
def create_course():
    """
    Create a new course.

    POST /api/courses

    Expected JSON:
    {
        "name": "Learn Flask",
        "description": "Build REST APIs with Flask",
        "target_date": "2026-12-31",
        "status": "Not Started"
    }
    """
    data, request_error = get_json_request_body()

    if request_error or data is None:
        return jsonify({"error": request_error}), 400

    validation_error = validate_course_data(data)

    if validation_error:
        return jsonify({"error": validation_error}), 400

    try:
        courses = read_courses()

        new_course = {
            "id": get_next_course_id(courses),
            "name": data["name"].strip(),
            "description": data["description"].strip(),
            "target_date": data["target_date"],
            "status": data["status"],
            "created_at": current_timestamp(),
        }

        courses.append(new_course)
        write_courses(courses)

    except (OSError, ValueError) as error:
        return jsonify({
            "error": "Could not save course data",
            "details": str(error),
        }), 500

    return jsonify(new_course), 201


@app.route("/api/courses", methods=["GET"])
@app.route("/api/courses/", methods=["GET"])
def get_all_courses():
    """
    Return all courses.

    GET /api/courses
    """
    try:
        courses = read_courses()
    except (OSError, ValueError) as error:
        return jsonify({
            "error": "Could not read course data",
            "details": str(error),
        }), 500

    return jsonify(courses), 200


@app.route("/api/courses/stats", methods=["GET"])
@app.route("/api/courses/stats/", methods=["GET"])
def get_course_stats():
    """
    Return statistics about all courses.

    GET /api/courses/stats

    Example response:
    {
        "total_courses": 3,
        "by_status": {
            "Not Started": 1,
            "In Progress": 1,
            "Completed": 1
        }
    }
    """
    try:
        courses = read_courses()
    except (OSError, ValueError) as error:
        return jsonify({
            "error": "Could not read course data",
            "details": str(error),
        }), 500

    # Start every valid status at 0 so all three always appear in the response.
    by_status = {
        "Not Started": 0,
        "In Progress": 0,
        "Completed": 0,
    }

    for course in courses:
        status = course.get("status")

        if status in by_status:
            by_status[status] += 1

    return jsonify({
        "total_courses": len(courses),
        "by_status": by_status,
    }), 200


@app.route("/api/courses/<int:course_id>", methods=["GET"])
@app.route("/api/courses/<int:course_id>/", methods=["GET"])
def get_course(course_id):
    """
    Return one course by ID.

    GET /api/courses/1
    """
    try:
        courses = read_courses()
    except (OSError, ValueError) as error:
        return jsonify({
            "error": "Could not read course data",
            "details": str(error),
        }), 500

    course = find_course(courses, course_id)

    if course is None:
        return jsonify({
            "error": f"Course with ID {course_id} was not found"
        }), 404

    return jsonify(course), 200


@app.route("/api/courses/<int:course_id>", methods=["PUT"])
@app.route("/api/courses/<int:course_id>/", methods=["PUT"])
def update_course(course_id):
    """
    Update one or more editable fields of an existing course.

    PUT /api/courses/1

    The request may include any of:
    - name
    - description
    - target_date
    - status

    At least one field is required. Fields that are not sent are left
    unchanged. The ID and created_at timestamp cannot be changed.
    """
    data, request_error = get_json_request_body()

    if request_error or data is None:
        return jsonify({"error": request_error}), 400

    validation_error = validate_course_data(data, partial=True)

    if validation_error:
        return jsonify({"error": validation_error}), 400

    try:
        courses = read_courses()
    except (OSError, ValueError) as error:
        return jsonify({
            "error": "Could not read course data",
            "details": str(error),
        }), 500

    course = find_course(courses, course_id)

    if course is None:
        return jsonify({
            "error": f"Course with ID {course_id} was not found"
        }), 404

    # Update only the editable fields that were sent.
    for field in ("name", "description"):
        if field in data:
            course[field] = data[field].strip()

    for field in ("target_date", "status"):
        if field in data:
            course[field] = data[field]

    try:
        write_courses(courses)
    except OSError as error:
        return jsonify({
            "error": "Could not update course data",
            "details": str(error),
        }), 500

    return jsonify(course), 200


@app.route("/api/courses/<int:course_id>", methods=["DELETE"])
@app.route("/api/courses/<int:course_id>/", methods=["DELETE"])
def delete_course(course_id):
    """
    Delete a course by ID.

    DELETE /api/courses/1
    """
    try:
        courses = read_courses()
    except (OSError, ValueError) as error:
        return jsonify({
            "error": "Could not read course data",
            "details": str(error),
        }), 500

    course = find_course(courses, course_id)

    if course is None:
        return jsonify({
            "error": f"Course with ID {course_id} was not found"
        }), 404

    # Create a new list that excludes the course being deleted.
    remaining_courses = [
        item for item in courses
        if item.get("id") != course_id
    ]

    try:
        write_courses(remaining_courses)
    except OSError as error:
        return jsonify({
            "error": "Could not delete course",
            "details": str(error),
        }), 500

    return jsonify({
        "message": f"Course with ID {course_id} was deleted"
    }), 200


# -----------------------------------------------------------------------------
# Application entry point
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    # Create courses.json when the application starts, if necessary.
    try:
        create_data_file_if_missing()
    except OSError as error:
        print(f"Warning: {error}")

    # debug=True is useful while learning.
    # Set debug=False when deploying the application.
    app.run(debug=True)