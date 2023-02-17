pipeline {
    agent any
    
    stages {
        stage('Build') {
            sh 'docker build -t microblog:latest .'
        }
    }
}
