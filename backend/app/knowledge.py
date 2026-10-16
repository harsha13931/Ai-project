"""Knowledge bank: skill topics, keyword detectors, and multiple-choice questions.

Each topic has 5 questions so the user can choose how many to attempt.
Topics found on a resume draw more questions (to verify claimed skills);
topics not found draw fewer (to probe gaps).
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
            {
                "q": "What is the output of `type(lambda x: x)`?",
                "options": ["<class 'lambda'>", "<class 'function'>", "<class 'method'>", "SyntaxError"],
                "answer": 1,
                "explain": "A lambda expression creates a function object. Python has no separate 'lambda' type.",
            },
            {
                "q": "Which keyword creates a generator function in Python?",
                "options": ["return", "yield", "generate", "async"],
                "answer": 1,
                "explain": "A function containing 'yield' becomes a generator function that returns an iterator.",
            },
            {
                "q": "What does the `@staticmethod` decorator do?",
                "options": [
                    "Makes the method private",
                    "Lets the method be called without an instance and receives no implicit first argument",
                    "Makes the method run at import time",
                    "Binds the method to the class instead of the instance",
                ],
                "answer": 1,
                "explain": "A static method receives no 'self' or 'cls'. @classmethod receives the class as the first argument.",
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
            {
                "q": "What does a database index primarily improve?",
                "options": ["Write speed", "Storage efficiency", "Read query speed", "Data integrity"],
                "answer": 2,
                "explain": "Indexes speed up reads by letting the engine locate rows without a full table scan, at the cost of slower writes.",
            },
            {
                "q": "What does ACID stand for in databases?",
                "options": [
                    "Automated, Consistent, Isolated, Durable",
                    "Atomicity, Consistency, Isolation, Durability",
                    "Atomic, Cached, Indexed, Distributed",
                    "Aggregated, Computed, Integrated, Deployed",
                ],
                "answer": 1,
                "explain": "ACID guarantees that transactions are atomic, consistent, isolated and durable.",
            },
            {
                "q": "Which SQL window function returns a sequential integer for each row within a partition?",
                "options": ["RANK()", "DENSE_RANK()", "ROW_NUMBER()", "NTILE()"],
                "answer": 2,
                "explain": "ROW_NUMBER() assigns a unique sequential integer. RANK() can produce gaps on ties.",
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
            {
                "q": "What is a Type I error?",
                "options": [
                    "Failing to reject a false null hypothesis",
                    "Rejecting a true null hypothesis",
                    "Choosing the wrong test",
                    "Having too small a sample",
                ],
                "answer": 1,
                "explain": "Type I error (false positive) means rejecting H0 when it is actually true. Type II is failing to reject a false H0.",
            },
            {
                "q": "What does the standard deviation measure?",
                "options": [
                    "The centre of the data",
                    "The spread of data around the mean",
                    "The skewness of the distribution",
                    "The number of outliers",
                ],
                "answer": 1,
                "explain": "Standard deviation quantifies how much individual values deviate from the mean on average.",
            },
            {
                "q": "In a normal distribution, approximately what percentage of data falls within 2 standard deviations of the mean?",
                "options": ["68%", "90%", "95%", "99%"],
                "answer": 2,
                "explain": "The 68-95-99.7 rule: about 95% of data lies within 2 standard deviations in a normal distribution.",
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
            {
                "q": "What is the bias-variance tradeoff?",
                "options": [
                    "Choosing between speed and accuracy",
                    "Balancing model complexity: too simple underfits (high bias), too complex overfits (high variance)",
                    "Deciding between CPU and GPU training",
                    "Trading training time for inference speed",
                ],
                "answer": 1,
                "explain": "High bias = underfitting; high variance = overfitting. Good models balance both.",
            },
            {
                "q": "Which metric is best for evaluating a classification model with heavily imbalanced classes?",
                "options": ["Accuracy", "F1 score", "Mean squared error", "R-squared"],
                "answer": 1,
                "explain": "With imbalanced classes, accuracy is misleading. F1 balances precision and recall for the minority class.",
            },
            {
                "q": "What technique helps prevent overfitting in a neural network?",
                "options": [
                    "Adding more layers",
                    "Increasing the learning rate",
                    "Dropout regularisation",
                    "Removing the validation set",
                ],
                "answer": 2,
                "explain": "Dropout randomly disables neurons during training, forcing the network to learn redundant representations.",
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
            {
                "q": "What is a closure in JavaScript?",
                "options": [
                    "A way to close browser windows",
                    "A function that retains access to its outer scope even after the outer function has returned",
                    "A method for closing database connections",
                    "A design pattern for singleton objects",
                ],
                "answer": 1,
                "explain": "A closure is a function bundled with its lexical environment, retaining access to outer variables.",
            },
            {
                "q": "What does `Array.prototype.reduce` do?",
                "options": [
                    "Removes elements from an array",
                    "Reduces the array to a single value by applying a function cumulatively",
                    "Sorts the array in descending order",
                    "Filters out falsy values",
                ],
                "answer": 1,
                "explain": "reduce applies a function against an accumulator and each element, reducing the array to one value.",
            },
            {
                "q": "What is the event loop in JavaScript?",
                "options": [
                    "A for-loop that runs events",
                    "A mechanism that handles async callbacks by checking the call stack and task queue",
                    "A DOM event listener",
                    "A loop that polls the server for updates",
                ],
                "answer": 1,
                "explain": "The event loop checks if the call stack is empty, then pushes the next callback from the task queue.",
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
            {
                "q": "What is horizontal scaling?",
                "options": [
                    "Adding more CPU and RAM to one machine",
                    "Adding more machines to share the load",
                    "Optimising queries to run faster",
                    "Compressing data to save space",
                ],
                "answer": 1,
                "explain": "Horizontal scaling (scaling out) adds more machines. Vertical scaling (scaling up) adds resources to one machine.",
            },
            {
                "q": "What problem does a message queue (like Kafka or RabbitMQ) solve?",
                "options": [
                    "It replaces the database",
                    "It decouples producers and consumers, buffering work and handling spikes",
                    "It encrypts messages in transit",
                    "It serves static files faster",
                ],
                "answer": 1,
                "explain": "Message queues decouple services, smooth traffic spikes, and allow async processing.",
            },
            {
                "q": "What is database sharding?",
                "options": [
                    "Backing up the database to multiple locations",
                    "Splitting data across multiple database instances based on a key",
                    "Encrypting individual database columns",
                    "Running read replicas for faster queries",
                ],
                "answer": 1,
                "explain": "Sharding partitions data by a shard key so each instance holds a subset, allowing horizontal scale.",
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
            {
                "q": "What is Infrastructure as Code (IaC)?",
                "options": [
                    "Writing application code that runs on servers",
                    "Managing infrastructure through machine-readable definition files instead of manual setup",
                    "Using only command-line interfaces",
                    "Coding directly on production servers",
                ],
                "answer": 1,
                "explain": "IaC (Terraform, CloudFormation) lets you version, review and reproduce infrastructure like application code.",
            },
            {
                "q": "What is the difference between a container and a virtual machine?",
                "options": [
                    "Containers are larger and slower",
                    "Containers share the host OS kernel and are lighter; VMs include a full guest OS",
                    "Virtual machines are more portable",
                    "There is no difference",
                ],
                "answer": 1,
                "explain": "Containers share the host kernel (lighter, faster startup). VMs virtualise the full hardware stack.",
            },
            {
                "q": "What does Kubernetes primarily do?",
                "options": [
                    "Builds container images",
                    "Orchestrates, scales and manages containerised workloads",
                    "Provides a code editor",
                    "Replaces DNS servers",
                ],
                "answer": 1,
                "explain": "Kubernetes automates deployment, scaling and operation of container clusters.",
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
            {
                "q": "When should you use a pie chart?",
                "options": [
                    "To show trends over time",
                    "To compare parts of a whole when there are very few categories (2-3)",
                    "To display correlation between two variables",
                    "To show distributions of continuous data",
                ],
                "answer": 1,
                "explain": "Pie charts work for part-to-whole with very few slices. Bar charts are better for more categories.",
            },
            {
                "q": "What is the data-ink ratio principle?",
                "options": [
                    "Use as many colours as possible",
                    "Maximise the share of ink used to show data, minimise non-data ink",
                    "Always print charts in black ink only",
                    "Make charts as small as possible",
                ],
                "answer": 1,
                "explain": "Edward Tufte's principle: remove chart junk and let the data stand out clearly.",
            },
            {
                "q": "Which chart type is best for showing the distribution of a single continuous variable?",
                "options": ["Bar chart", "Histogram", "Pie chart", "Treemap"],
                "answer": 1,
                "explain": "A histogram bins continuous values to show the shape, centre and spread of a distribution.",
            },
        ],
    },
}
