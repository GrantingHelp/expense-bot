# Start with official Python 3.11 on a lightweight Linux base
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first (we'll create this next)
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all bot files into the container
COPY bot.py .
COPY receipt_processor.py .
COPY trip_log.py .
COPY reconciliation.py .
COPY pdf_generator.py .
COPY help_handler.py .

# Create folders the bot needs
RUN mkdir -p temp_photos photos

# Tell Docker to run the bot when the container starts
CMD ["python3", "bot.py"]