// ClearOps CI. Jenkins builds, tests and pushes images, then records the new
// version in the config repo (clearops-gitops). ArgoCD does the deploy.
// Jenkins has NO cluster credentials. Compare Module 8, which deployed over SSH.

pipeline {
  agent any

  options {
    timestamps()
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '15'))
  }

  // No public address for GitHub webhooks, so Jenkins checks GitHub every ~2 minutes.
  // Pull, not push: the same idea as ArgoCD polling git (Concept 9).
  triggers { pollSCM('H/2 * * * *') }

  environment {
    REGISTRY     = 'crystalvivian'
    GITOPS_REPO  = 'git@github.com:vivianokose/clearops-gitops.git'
    OVERLAY      = 'apps/clearops/overlays/dev'
    // GitHub's published ed25519 host key. Pinned, so we never trust an impostor.
    // Fingerprint (checked in the pipeline): SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU
    GITHUB_HOSTKEY = 'github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl'
  }

  stages {

    stage('Prepare SSH') {
      steps {
        sh '''
          echo "$GITHUB_HOSTKEY" > "$WORKSPACE/.known_hosts"
          ssh-keygen -lf "$WORKSPACE/.known_hosts" | grep -q 'SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU' \
            || { echo "GitHub host key fingerprint mismatch. Stopping."; exit 1; }
          echo "GitHub host key pinned and verified."
        '''
      }
    }

    stage('Compute version') {
      steps {
        withCredentials([sshUserPrivateKey(credentialsId: 'gitops-deploy-key', keyFileVariable: 'KEY')]) {
          script {
            // The config repo is the record of what is deployed, so the current
            // version is read from there. The commit prefix decides the bump.
            def out = sh(returnStdout: true, script: '''
              export GIT_SSH_COMMAND="ssh -i $KEY -o UserKnownHostsFile=$WORKSPACE/.known_hosts -o StrictHostKeyChecking=yes"
              rm -rf gitops && git clone --quiet --depth 1 "$GITOPS_REPO" gitops

              # Render the overlay and read the API image tag from the result, so the
              # layout of kustomization.yaml (newTag, newName, field order) does not matter.
              CURRENT=$(kustomize build "gitops/$OVERLAY" | grep -o "image: $REGISTRY/clearops-api:[0-9.]*" | head -1 | cut -d: -f3)
              echo "$CURRENT" | grep -Eq '^[0-9]+[.][0-9]+[.][0-9]+$' \\
                || { echo "Could not read the deployed version (got '$CURRENT'). Stopping." >&2; exit 1; }
              MSG=$(git log -1 --pretty=%s)
              IFS=. read -r MA MI PA <<EOV
$CURRENT
EOV
              case "$MSG" in
                *'!:'*|*'BREAKING CHANGE'*) NEXT="$((MA+1)).0.0" ;;
                feat*)                      NEXT="$MA.$((MI+1)).0" ;;
                fix*)                       NEXT="$MA.$MI.$((PA+1))" ;;
                *)                          NEXT="" ;;
              esac

              # Never reuse a published tag. After a rollback, git says 1.1.0 again,
              # but 1.1.1 already exists on Docker Hub (and in the cluster's image cache).
              # Reusing it would ship the old bad image under a "new" release.
              if [ -n "$NEXT" ]; then
                while docker manifest inspect "$REGISTRY/clearops-api:$NEXT" >/dev/null 2>&1; do
                  echo "Tag $NEXT is already published. Skipping to the next patch version." >&2
                  NEXT="${NEXT%.*}.$(( ${NEXT##*.} + 1 ))"
                done
              fi
              echo "$CURRENT|$NEXT|$MSG"
            ''').trim()

            def parts = out.split('\\|', 3)
            env.CURRENT_VERSION = parts[0]
            env.NEW_VERSION     = parts[1]
            env.RELEASE         = env.NEW_VERSION ? 'true' : 'false'
            echo "Deployed now: ${env.CURRENT_VERSION}. Commit: \"${parts[2]}\". Next: ${env.NEW_VERSION ?: 'no release (not feat/fix)'}"
          }
        }
      }
    }

    stage('Lint Dockerfiles') {
      when { expression { env.RELEASE == 'true' } }
      steps {
        // Fed through stdin, so no volume mounts are needed (Jenkins talks to the
        // host's Docker, which cannot see paths inside the Jenkins container).
        sh '''
          docker run --rm -i hadolint/hadolint:v2.12.0 hadolint --failure-threshold error - < services/api/Dockerfile
          docker run --rm -i hadolint/hadolint:v2.12.0 hadolint --failure-threshold error - < services/frontend/Dockerfile
        '''
      }
    }

    stage('Build') {
      when { expression { env.RELEASE == 'true' } }
      steps {
        sh '''
          docker build --build-arg APP_VERSION="$NEW_VERSION" -t "$REGISTRY/clearops-api:$NEW_VERSION" services/api
          docker build -t "$REGISTRY/clearops-frontend:$NEW_VERSION" services/frontend
        '''
      }
    }

    stage('Test image') {
      when { expression { env.RELEASE == 'true' } }
      steps {
        // Start the API, ask /health which version it thinks it is, then clean up.
        sh '''
          NAME="clearops-api-test-$BUILD_NUMBER"
          docker run -d --name "$NAME" "$REGISTRY/clearops-api:$NEW_VERSION"
          trap 'docker rm -f "$NAME" >/dev/null 2>&1' EXIT
          sleep 3
          RESPONSE=$(docker exec "$NAME" python3 -c "import urllib.request;print(urllib.request.urlopen('http://localhost:8080/health').read().decode())")
          echo "health: $RESPONSE"
          echo "$RESPONSE" | grep -q "\\"version\\": \\"$NEW_VERSION\\"" || { echo "Version mismatch"; exit 1; }
        '''
      }
    }

    stage('Push images') {
      when { expression { env.RELEASE == 'true' } }
      steps {
        withCredentials([usernamePassword(credentialsId: 'dockerhub-credentials',
                                          usernameVariable: 'DH_USER', passwordVariable: 'DH_TOKEN')]) {
          // Single quotes: the shell reads the secret, Groovy never sees it
          // (the secret-interpolation fix from Module 8).
          sh '''
            echo "$DH_TOKEN" | docker login -u "$DH_USER" --password-stdin
            docker push "$REGISTRY/clearops-api:$NEW_VERSION"
            docker push "$REGISTRY/clearops-frontend:$NEW_VERSION"
            docker logout
          '''
        }
      }
    }

    stage('Update GitOps repo') {
      when { expression { env.RELEASE == 'true' } }
      steps {
        withCredentials([sshUserPrivateKey(credentialsId: 'gitops-deploy-key', keyFileVariable: 'KEY')]) {
          sh '''
            export GIT_SSH_COMMAND="ssh -i $KEY -o UserKnownHostsFile=$WORKSPACE/.known_hosts -o StrictHostKeyChecking=yes"
            cd gitops
            git pull --quiet --rebase

            cd "$OVERLAY"
            # "name:tag" form changes only newTag (the "a=b:tag" form also adds a newName line).
            kustomize edit set image "$REGISTRY/clearops-api:$NEW_VERSION"
            kustomize edit set image "$REGISTRY/clearops-frontend:$NEW_VERSION"
            cd - >/dev/null

            git config user.name  "jenkins-local"
            git config user.email "jenkins@clearops.local"
            git add "$OVERLAY/kustomization.yaml"
            git commit -m "chore(dev): bump clearops to $NEW_VERSION" \
                       -m "Built by Jenkins #$BUILD_NUMBER from clearops-app $(git -C "$WORKSPACE" rev-parse --short HEAD)"

            # If someone else pushed meanwhile, rebase and try once more.
            git push origin HEAD:main || { git pull --rebase && git push origin HEAD:main; }
          '''
        }
        echo "Done. ArgoCD will deploy ${env.NEW_VERSION} to dev. Jenkins stops here."
      }
    }
  }

  post {
    always {
      sh 'rm -f "$WORKSPACE/.known_hosts"; docker image prune -f >/dev/null 2>&1 || true'
    }
  }
}
