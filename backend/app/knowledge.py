"""Knowledge bank: skill topics, keyword detectors, and multiple-choice questions.

Each topic has two questions. Topics found on a resume get both questions
(to verify claimed skills); topics not found get one question (to probe gaps).
"""

TOPICS = {
    "python": {
        "label": "Python",
        "keywords": ["python", "pandas", "numpy", "django", "flask", "fastapi"],
        "guidance": "Practice core data structures, comprehensions, and standard library idioms. Build a small CLI or API project to lock them in.",
        "questions": [
            {
                "q": "Which built-in Python data structure is immutable and can be used as a dictionary key?",
                "options": ["list", "dict", "tuple", "set"],
                "answer": 2,
                "explain": "Tuples are immutable and hashable (when their items are), so they can be dictionary keys. Lists, dicts and sets are mutable.",
            },
            {
                "q": "What does `[x * 2 for x in range(3) if x > 0]` evaluate to?",
                "options": ["[0, 2, 4]", "[2, 4]", "[1, 2]", "[4]"],
                "answer": 1,
                "explain": "range(3) yields 0, 1, 2. The filter keeps 1 and 2, and doubling gives [2, 4].",
            },
        ],
    },
    "sql": {
        "label": "SQL & Databases",
        "keywords": ["sql", "postgres", "postgresql", "mysql", "sqlite", "oracle", "t-sql"],
        "guidance": "Work through joins, aggregation and window functions on a real dataset. Explain query plans and indexes in your own words.",
        "questions": [
            {
                "q": "Which clause filters rows AFTER aggregation has been applied?",
                "options": ["WHERE", "GROUP BY", "HAVING", "ORDER BY"],
                "answer": 2,
                "explain": "WHERE filters rows before grouping; HAVING filters groups after aggregation.",
            },
            {
                "q": "Which JOIN returns every row from the left table even when there is no match on the right?",
                "options": ["INNER JOIN", "LEFT JOIN", "CROSS JOIN", "SELF JOIN"],
                "answer": 1,
                "explain": "A LEFT JOIN keeps all left-table rows and fills unmatched right-side columns with NULL.",
            },
        ],
    },
    "statistics": {
        "label": "Statistics",
        "keywords": ["statistics", "statistical", "hypothesis", "regression", "a/b test", "probability"],
        "guidance": "Revisit descriptive statistics, distributions, and hypothesis testing. Explain p-values and confidence intervals without jargon.",
        "questions": [
            {
                "q": "Which measure of central tendency is most affected by extreme outliers?",
                "options": ["Median", "Mode", "Mean", "Interquartile range"],
                "answer": 2,
                "explain": "The mean is pulled toward extreme values. The median and mode are robust, and IQR is a spread measure.",
            },
            {
                "q": "A p-value of 0.03 at a significance level of 0.05 means:",
                "options": [
                    "The null hypothesis is true with 97% probability",
                    "Data this extreme would occur about 3% of the time if the null hypothesis were true",
                    "The effect size is 3%",
                    "The test was run incorrectly",
                ],
                "answer": 1,
                "explain": "A p-value is P(data at least this extreme | H0). It is not the probability that H0 is true.",
            },
        ],
    },
    "machine_learning": {
        "label": "Machine Learning",
        "keywords": ["machine learning", "scikit-learn", "sklearn", "tensorflow", "pytorch", "deep learning", "xgboost", "nlp"],
        "guidance": "Learn the train/validation/test workflow, bias-variance tradeoff, and evaluation metrics. Re-implement one model end to end.",
        "questions": [
            {
                "q": "Which pattern most clearly indicates overfitting?",
                "options": [
                    "Low training error and low validation error",
                    "High training error and high validation error",
                    "Low training error but much higher validation error",
                    "High training error but low validation error",
                ],
                "answer": 2,
                "explain": "The model memorizes training data but fails to generalize, so validation error is much higher.",
            },
            {
                "q": "Why do we split data into train, validation and test sets?",
                "options": [
                    "To make the dataset larger",
                    "To evaluate generalization on data not used for fitting or tuning",
                    "To speed up training only",
                    "To remove missing values",
                ],
                "answer": 1,
                "explain": "Keeping evaluation data separate from fitting and tuning gives an honest estimate of performance on unseen data.",
            },
        ],
    },
    "javascript": {
        "label": "JavaScript & Frontend",
        "keywords": ["javascript", "typescript", "react", "node.js", "nodejs", "vue", "angular"],
        "guidance": "Focus on closures, the event loop, promises and async/await. Build one interactive UI and test it.",
        "questions": [
            {
                "q": "What does the strict equality operator `===` check in JavaScript?",
                "options": [
                    "Value only, with type coercion",
                    "Value and type, without type coercion",
                    "Reference identity for all types",
                    "Only that both sides are truthy",
                ],
                "answer": 1,
                "explain": "=== compares both value and type with no coercion. == allows coercion.",
            },
            {
                "q": "What is the correct way to use the result of an asynchronous fetch request in modern JavaScript?",
                "options": [
                    "Read the value synchronously right after calling fetch",
                    "Use await inside an async function (or chain with .then)",
                    "Store the promise in a var and use it as data",
                    "Wrap the call in setTimeout with 0 ms",
                ],
                "answer": 1,
                "explain": "fetch returns a promise. await or .then gives you the resolved value once it is ready.",
            },
        ],
    },
    "system_design": {
        "label": "System Design",
        "keywords": ["system design", "microservices", "distributed systems", "scalability", "load balancing", "kafka"],
        "guidance": "Practice designing a URL shortener or feed system. Cover caching, partitioning, replication, and the CAP tradeoff.",
        "questions": [
            {
                "q": "What is the main purpose of a cache in a system design?",
                "options": [
                    "Durable long-term storage",
                    "Reducing latency and database load by serving frequent reads from fast storage",
                    "Encrypting data at rest",
                    "Balancing traffic between regions",
                ],
                "answer": 1,
                "explain": "Caches keep hot data close to the consumer, cutting latency and load on the primary store.",
            },
            {
                "q": "In the CAP theorem, during a network partition a distributed system must choose between:",
                "options": [
                    "Latency and throughput",
                    "Consistency and availability",
                    "Security and speed",
                    "Storage and compute",
                ],
                "answer": 1,
                "explain": "Under a partition you can keep responding (availability) or keep replicas identical (consistency), not both.",
            },
        ],
    },
    "cloud_devops": {
        "label": "Cloud & DevOps",
        "keywords": ["aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ci/cd", "devops"],
        "guidance": "Containerize one app with Docker, add a CI pipeline that runs tests, and deploy it to a managed cloud service.",
        "questions": [
            {
                "q": "What is the primary purpose of a Dockerfile?",
                "options": [
                    "Defining how to build a container image",
                    "Managing running Kubernetes pods",
                    "Storing application logs",
                    "Defining DNS records",
                ],
                "answer": 0,
                "explain": "A Dockerfile is a recipe for building an immutable image. Kubernetes runs containers; it does not build them.",
            },
            {
                "q": "What does a CI/CD pipeline primarily automate?",
                "options": [
                    "Building, testing and deploying code changes",
                    "Hiring and onboarding engineers",
                    "Sizing hardware purchases",
                    "Writing product requirements",
                ],
                "answer": 0,
                "explain": "Continuous integration builds and tests every change. Continuous delivery/deployment ships it.",
            },
        ],
    },
    "data_visualization": {
        "label": "Data Visualization",
        "keywords": ["tableau", "power bi", "powerbi", "looker", "matplotlib", "data visualization", "dashboard"],
        "guidance": "Pick chart types by the question being asked. Build one dashboard that leads with a single key metric.",
        "questions": [
            {
                "q": "Which chart is generally best for showing a trend over time?",
                "options": ["Pie chart", "Line chart", "Unordered scatter plot of categories", "100% stacked bar"],
                "answer": 1,
                "explain": "Line charts map time to the x-axis and make direction and change easy to read.",
            },
            {
                "q": "Which practice most improves the clarity of a dashboard?",
                "options": [
                    "Using a different color for every series",
                    "Adding 3D effects to charts",
                    "Leading with the key metric and giving each visual one message",
                    "Including every available field",
                ],
                "answer": 2,
                "explain": "Clear hierarchy and one message per visual reduce cognitive load for the reader.",
            },
        ],
    },
}
