document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById('spriteCanvas');
    const ctx = canvas.getContext('2d');
    const modelSelectDropdown = document.getElementById('spritesheet-select');
    const nextModelBtn = document.getElementById('nextModelBtn');
    const toggleParticlesBtn = document.getElementById('toggleParticlesBtn');
    const toggleMovementLockBtn = document.getElementById('toggleMovementLockBtn');
    const animationSpeedInput = document.getElementById('animation-speed-input');
    const animationSpeedValueDisplay = document.getElementById('animation-speed-value');
    const movementSpeedInput = document.getElementById('movement-speed-input');
    const movementSpeedValueDisplay = document.getElementById('movement-speed-value');

    const charModelNameDisplay = document.getElementById('char-model-name');
    const charPosDisplay = document.getElementById('char-pos');
    const charAngleDegreesDisplay = document.getElementById('char-angle-degrees');
    const charAngleIndexDisplay = document.getElementById('char-angle-idx');
    const charAnimFrameDisplay = document.getElementById('char-anim-frame');
    const charStatusDisplay = document.getElementById('char-status');
    const movementLockStatusDisplay = document.getElementById('movement-lock-status');

    const SPRITESHEET_BASE_URL = 'assets/spritesheets/';
    const MAIN_MANIFEST_FILE = SPRITESHEET_BASE_URL + 'manifest_spritesheets.json';
    const MAX_MODELS_TO_DISPLAY = 25;

    let characters = [];
    let characterModelsData = {};
    let activeCharacterId = null;
    let globalParticlesEnabled = true;
    let globalMovementLocked = false;
    let gameLoopRequestId = null;
    let assetsLoading = false;

    const keys = {
        ArrowUp: false, ArrowDown: false, ArrowLeft: false, ArrowRight: false,
        w: false, a: false, s: false, d: false,
        ' ': false,
        Shift: false,
        r: false
    };
    let rKeyJustPressed = false;

    let lastMouseAngleDegrees = 0;
    let isMouseOverCanvas = false;

    class Particle {
        constructor(x, y, charHeight) {
            this.x = x + (Math.random() - 0.5) * (charHeight * 0.1);
            this.y = y + (Math.random() - 0.5) * (charHeight * 0.05);
            this.size = Math.random() * 3 + 1;
            this.speedX = (Math.random() - 0.5) * 1.5;
            this.speedY = Math.random() * -1 - 0.5;
            this.life = Math.random() * 40 + 20;
            this.initialLife = this.life;
            this.color = `rgba(180, 160, 140, ${Math.random() * 0.4 + 0.3})`;
        }
        update() {
            this.x += this.speedX;
            this.y += this.speedY;
            this.speedY += 0.05;
            this.life--;
            const alpha = (this.life / this.initialLife) * 0.7;
            this.color = `rgba(180, 160, 140, ${Math.max(0, alpha)})`;
        }
        draw(ctx) {
            if (this.life > 0) {
                ctx.fillStyle = this.color;
                ctx.beginPath();
                ctx.arc(this.x, this.y, this.size, 0, Math.PI * 2);
                ctx.fill();
            }
        }
    }

    function isAnyMovementKeyPressed() {
        return keys.ArrowUp || keys.ArrowDown || keys.ArrowLeft || keys.ArrowRight ||
               keys.w || keys.s || keys.a || keys.d;
    }

    class Character {
        constructor(x, y, modelId, modelAnimationsData) {
            this.x = x;
            this.y = y;
            this.id = modelId;
            this.animations = {};
            this.modelAnimationsData = modelAnimationsData;

            this.currentAngleIndex = 0;
            this.animationSpeed = parseFloat(animationSpeedInput.value);
            this.facingAngleDegrees = 90;

            this.baseMovementSpeed = parseFloat(movementSpeedInput.value);
            this.movementSpeed = this.baseMovementSpeed;

            this.isMovingByInput = false;
            this.currentAnimationName = "Idle";
            this.isCurrentAnimationLooping = true;
            this.onAnimationCompleteCallback = null;

            this.isFlying = false;
            this.flySpeedFactor = 1.3;
            this.isDancing = false;

            this.spriteWidth = 0;
            this.spriteHeight = 0;

            this.particles = [];
            this.particleEmitCounter = 0;
            this.particleEmitRate = 3;
        }

        async loadAssets() {
            const assetLoadPromises = [];
            for (const animName in this.modelAnimationsData) {
                const entry = this.modelAnimationsData[animName];
                if (entry && entry.metadata_file && entry.spritesheet_file) {
                    assetLoadPromises.push(
                        fetch(SPRITESHEET_BASE_URL + entry.metadata_file)
                            .then(response => {
                                if (!response.ok) throw new Error(`Metadata not found: ${entry.metadata_file} for ${this.id}-${animName}`);
                                return response.json();
                            })
                            .then(meta => {
                                return new Promise((resolve, reject) => {
                                    const image = new Image();
                                    image.src = SPRITESHEET_BASE_URL + entry.spritesheet_file;
                                    image.onload = () => {
                                        this.animations[animName] = {
                                            image: image, meta: meta, timer: 0, currentFrameIndex: 0,
                                        };
                                        if (!this.spriteWidth && animName.toLowerCase() === 'idle') {
                                            this.spriteWidth = meta.sprite_width_px;
                                            this.spriteHeight = meta.sprite_height_px;
                                        } else if (!this.spriteWidth && Object.keys(this.animations).length ===1) {
                                            this.spriteWidth = meta.sprite_width_px;
                                            this.spriteHeight = meta.sprite_height_px;
                                        }
                                        resolve();
                                    };
                                    image.onerror = () => reject(new Error(`Image ${entry.spritesheet_file} for ${this.id}-${animName} loading error.`));
                                });
                            })
                    );
                } else { console.warn(`Missing data for animation ${animName} for model ${this.id}`); }
            }
            await Promise.all(assetLoadPromises);
            this.updateAngleIndexFromDegrees(this.facingAngleDegrees);
            if (!this.animations["Idle"] && this.animations["Walking"]) {
                this.currentAnimationName = "Walking";
            } else if (!this.animations["Idle"]) {
                const firstAvailableAnim = Object.keys(this.animations)[0];
                if (firstAvailableAnim) this.currentAnimationName = firstAvailableAnim;
                else console.error("No animations loaded for " + this.id);
            }
            if (!this.spriteWidth && this.animations[this.currentAnimationName]) {
                this.spriteWidth = this.animations[this.currentAnimationName].meta.sprite_width_px;
                this.spriteHeight = this.animations[this.currentAnimationName].meta.sprite_height_px;
            }

            return this;
        }

        playAnimation(animationName, loop = true, onComplete = null) {
            if (!this.animations[animationName]) {
                console.warn(`Animation "${animationName}" not found for ${this.id}. Falling back to Idle/first available animation.`);
                const fallbackAnim = this.animations["Idle"] ? "Idle" : Object.keys(this.animations)[0];
                if (fallbackAnim) {
                    animationName = fallbackAnim;
                } else {
                    console.error(`No fallback animation found for ${this.id}.`);
                    return;
                }
            }

            if (this.currentAnimationName === animationName && this.isCurrentAnimationLooping === loop) {
                if(loop) {
                } else {
                    this.animations[animationName].currentFrameIndex = 0;
                    this.animations[animationName].timer = 0;
                }
            } else {
                this.animations[animationName].currentFrameIndex = 0;
                this.animations[animationName].timer = 0;
            }

            this.currentAnimationName = animationName;
            this.isCurrentAnimationLooping = loop;
            this.onAnimationCompleteCallback = onComplete;

            if (animationName === "Roll") {
                this.isFlying = true;
                this.isDancing = false;
            } else if (animationName === "Dance") {
                this.isDancing = true;
                this.isFlying = false;
            } else {
                this.isFlying = false;
                this.isDancing = false;
            }

            this.spriteWidth = this.animations[animationName].meta.sprite_width_px;
            this.spriteHeight = this.animations[animationName].meta.sprite_height_px;
        }

        updateAngleIndexFromDegrees(degrees) {
            const currentAnimMeta = this.animations[this.currentAnimationName]?.meta;
            if (!currentAnimMeta || currentAnimMeta.total_angles_or_rows === 0) return;
            this.facingAngleDegrees = ((degrees % 360) + 360) % 360;
            const numSheetAngles = currentAnimMeta.total_angles_or_rows;
            if (numSheetAngles === 8) {
                 if (this.facingAngleDegrees >= 67.5 && this.facingAngleDegrees < 112.5) this.currentAngleIndex = 0;
                 else if (this.facingAngleDegrees >= 112.5 && this.facingAngleDegrees < 157.5) this.currentAngleIndex = 7;
                 else if (this.facingAngleDegrees >= 157.5 && this.facingAngleDegrees < 202.5) this.currentAngleIndex = 6;
                 else if (this.facingAngleDegrees >= 202.5 && this.facingAngleDegrees < 247.5) this.currentAngleIndex = 5;
                 else if (this.facingAngleDegrees >= 247.5 && this.facingAngleDegrees < 292.5) this.currentAngleIndex = 4;
                 else if (this.facingAngleDegrees >= 292.5 && this.facingAngleDegrees < 337.5) this.currentAngleIndex = 3;
                 else if (this.facingAngleDegrees >= 337.5 || this.facingAngleDegrees < 22.5) this.currentAngleIndex = 2;
                 else if (this.facingAngleDegrees >= 22.5 && this.facingAngleDegrees < 67.5) this.currentAngleIndex = 1;
                 else { this.currentAngleIndex = 0; }
            } else if (numSheetAngles > 0) {
                const anglePerSpriteRow = 360 / numSheetAngles;
                let adjustedDegrees = (this.facingAngleDegrees + anglePerSpriteRow / 2) % 360;
                this.currentAngleIndex = Math.floor(adjustedDegrees / anglePerSpriteRow);
                this.currentAngleIndex = Math.min(this.currentAngleIndex, numSheetAngles - 1);
            }
        }

        update() {
            this.animationSpeed = parseFloat(animationSpeedInput.value);
            this.isMovingByInput = isAnyMovementKeyPressed();

            const currentAnim = this.animations[this.currentAnimationName];
            if (!currentAnim || !currentAnim.meta) return;

            currentAnim.timer += this.animationSpeed;
            if (currentAnim.timer >= 1) {
                currentAnim.timer = 0;
                currentAnim.currentFrameIndex++;
                if (currentAnim.currentFrameIndex >= currentAnim.meta.total_animation_frames_per_angle_or_columns) {
                    if (this.isCurrentAnimationLooping) {
                        currentAnim.currentFrameIndex = 0;
                    } else {
                        currentAnim.currentFrameIndex = currentAnim.meta.total_animation_frames_per_angle_or_columns - 1;
                        if (this.onAnimationCompleteCallback) {
                            this.onAnimationCompleteCallback();
                            this.onAnimationCompleteCallback = null;
                        }
                    }
                }
            }

            if (this.currentAnimationName === "Walking" && this.isMovingByInput && globalParticlesEnabled) {
                this.particleEmitCounter++;
                if (this.particleEmitCounter >= this.particleEmitRate) {
                    this.particleEmitCounter = 0;
                    const particleX = this.x;
                    const particleY = this.y + (this.spriteHeight || currentAnim.meta.sprite_height_px) / 2 * 0.8;
                    this.particles.push(new Particle(particleX, particleY, (this.spriteHeight || currentAnim.meta.sprite_height_px)));
                }
            }
            this.particles.forEach(p => p.update());
            this.particles = this.particles.filter(p => p.life > 0);
        }

        draw(ctx) {
            this.particles.forEach(p => p.draw(ctx));
            const currentAnim = this.animations[this.currentAnimationName];
            if (!currentAnim || !currentAnim.image || !currentAnim.meta || !currentAnim.image.complete || currentAnim.image.naturalWidth === 0) {
                return;
            }
            const sourceX = currentAnim.currentFrameIndex * currentAnim.meta.sprite_width_px;
            const sourceY = this.currentAngleIndex * currentAnim.meta.sprite_height_px;
            ctx.save();
            ctx.translate(this.x, this.y);
            ctx.drawImage(currentAnim.image,
                sourceX, sourceY,
                currentAnim.meta.sprite_width_px, currentAnim.meta.sprite_height_px,
                -currentAnim.meta.sprite_width_px / 2, -currentAnim.meta.sprite_height_px / 2,
                currentAnim.meta.sprite_width_px, currentAnim.meta.sprite_height_px);
            ctx.restore();
        }
    }

    function loadGameAssets() {
        if (assetsLoading) return;
        assetsLoading = true;
        characterModelsData = {};
        fetch(MAIN_MANIFEST_FILE)
            .then(response => { if (!response.ok) throw new Error(`Main manifest ${MAIN_MANIFEST_FILE} not found.`); return response.json(); })
            .then(mainManifestJson => {
                if (!Array.isArray(mainManifestJson) || mainManifestJson.length === 0) return Promise.reject("Empty or invalid main manifest");
                mainManifestJson.forEach(entry => {
                    if (!entry.model_and_animation_name) return;
                    const parts = entry.model_and_animation_name.split('_');
                    if (parts.length < 2) { console.warn(`Invalid format for model_and_animation_name: ${entry.model_and_animation_name}`); return; }
                    const modelBaseName = parts.slice(0, -1).join('_');
                    const animationType = parts[parts.length - 1];
                    if (!characterModelsData[modelBaseName]) characterModelsData[modelBaseName] = {};
                    characterModelsData[modelBaseName][animationType] = entry;
                });
                modelSelectDropdown.innerHTML = '';
                const loadPromises = [];
                let modelCount = 0;
                for (const modelId in characterModelsData) {
                    if (modelCount >= MAX_MODELS_TO_DISPLAY) break;
                    const option = document.createElement('option');
                    option.value = modelId; option.textContent = modelId;
                    modelSelectDropdown.appendChild(option);
                    const newChar = new Character(0, 0, modelId, characterModelsData[modelId]);
                    loadPromises.push(newChar.loadAssets());
                    modelCount++;
                }
                if (loadPromises.length === 0) return Promise.reject("No valid models to load after grouping.");
                return Promise.all(loadPromises);
            })
            .then(loadedCharacterInstances => {
                characters = loadedCharacterInstances.filter(c => c && Object.keys(c.animations).length > 0);
                if (characters.length === 0) { alert("No character spritesheets could be loaded."); assetsLoading = false; return; }
                const firstChar = characters[0];
                let baseSpriteWidth = 128;
                let baseSpriteHeight = 128;
                const firstCharIdleAnim = firstChar.animations["Idle"] || firstChar.animations[Object.keys(firstChar.animations)[0]];
                if (firstCharIdleAnim && firstCharIdleAnim.meta) {
                    baseSpriteWidth = firstCharIdleAnim.meta.sprite_width_px;
                    baseSpriteHeight = firstCharIdleAnim.meta.sprite_height_px;
                }

                canvas.width = Math.max(1200, baseSpriteWidth * Math.min(characters.length, 5) * 1.2);
                canvas.height = Math.max(600, baseSpriteHeight * 1.5);
                let spacing = baseSpriteWidth * 0.3;
                let totalWidthNeeded = characters.reduce((sum, char) => sum + (char.spriteWidth || baseSpriteWidth), 0) + (characters.length - 1) * spacing;
                let currentX = (canvas.width - totalWidthNeeded) / 2 + (characters[0]?.spriteWidth || baseSpriteWidth) / 2;
                if (characters.length === 1) currentX = canvas.width / 2;

                characters.forEach(char => {
                    char.x = currentX; char.y = canvas.height * 0.6;
                    currentX += (char.spriteWidth || baseSpriteWidth) + spacing;
                });
                activeCharacterId = characters[0].id;
                modelSelectDropdown.value = activeCharacterId;
                const activeCharInstance = getActiveCharacter();
                if (activeCharInstance) lastMouseAngleDegrees = activeCharInstance.facingAngleDegrees;
                updateInfoDisplay();
                assetsLoading = false;
                if (!gameLoopRequestId) gameLoop();
            })
            .catch(error => { console.error("Error during initialization:", error); alert("Initialization error: " + error.message); assetsLoading = false; });
    }

    function getActiveCharacter() {
        if (!activeCharacterId) return null;
        return characters.find(char => char.id === activeCharacterId);
    }

    function gameUpdate() {
        if (assetsLoading || characters.length === 0) return;
        const activeChar = getActiveCharacter();
        if (!activeChar) return;

        const wantsToMove = isAnyMovementKeyPressed();
        const isShiftPressed = keys.Shift;

        if (rKeyJustPressed) {
            if (activeChar.isDancing) {
                activeChar.isDancing = false;
                if (isShiftPressed) {
                    if (!activeChar.isFlying) {
                        activeChar.movementSpeed = activeChar.baseMovementSpeed * activeChar.flySpeedFactor;
                        activeChar.playAnimation("Roll", true);
                    }
                } else if (wantsToMove) {
                    activeChar.playAnimation("Walking");
                } else {
                    activeChar.playAnimation("Idle");
                }
            } else {
                if (!activeChar.animations["Dance"]) {
                    console.warn("Dance animation not available for " + activeChar.id);
                } else {
                    activeChar.playAnimation("Dance", true);
                    if(activeChar.isFlying) {
                         activeChar.movementSpeed = activeChar.baseMovementSpeed;
                    }
                }
            }
            rKeyJustPressed = false;
        }

        if (activeChar.isDancing && wantsToMove) {
            activeChar.isDancing = false;
        }

        if (isShiftPressed) {
            if (!activeChar.isFlying) {
                activeChar.movementSpeed = activeChar.baseMovementSpeed * activeChar.flySpeedFactor;
                activeChar.playAnimation("Roll", true);
            }
        } else {
            if (activeChar.isFlying) {
                activeChar.movementSpeed = activeChar.baseMovementSpeed;
                activeChar.isFlying = false;
                 if (wantsToMove) {
                    activeChar.playAnimation("Walking");
                } else {
                    activeChar.playAnimation("Idle");
                }
            }
        }

        if (!activeChar.isFlying && !activeChar.isDancing) {
            if (wantsToMove) {
                if (activeChar.currentAnimationName !== "Walking") {
                    activeChar.playAnimation("Walking");
                }
            } else {
                if (activeChar.currentAnimationName !== "Idle") {
                    activeChar.playAnimation("Idle");
                }
            }
        }

        let dx = 0, dy = 0;
        let currentSpeed = activeChar.movementSpeed;

        if (keys.ArrowUp || keys.w) dy -= currentSpeed;
        if (keys.ArrowDown || keys.s) dy += currentSpeed;
        if (keys.ArrowLeft || keys.a) dx -= currentSpeed;
        if (keys.ArrowRight || keys.d) dx += currentSpeed;

        if (wantsToMove && !globalMovementLocked) {
            activeChar.x += dx;
            activeChar.y += dy;
            const currentSpriteWidth = activeChar.spriteWidth || activeChar.animations[activeChar.currentAnimationName]?.meta.sprite_width_px || 0;
            const currentSpriteHeight = activeChar.spriteHeight || activeChar.animations[activeChar.currentAnimationName]?.meta.sprite_height_px || 0;
            activeChar.x = Math.max(currentSpriteWidth / 2, Math.min(activeChar.x, canvas.width - currentSpriteWidth / 2));
            activeChar.y = Math.max(currentSpriteHeight / 2, Math.min(activeChar.y, canvas.height - currentSpriteHeight / 2));
        }

        if (wantsToMove && !isMouseOverCanvas) {
            let movementAngle = (Math.atan2(dy, dx) * (180 / Math.PI) + 360) % 360;
            activeChar.updateAngleIndexFromDegrees(movementAngle);
        } else if (isMouseOverCanvas) {
            activeChar.updateAngleIndexFromDegrees(lastMouseAngleDegrees);
        }

        characters.forEach(char => char.update());
        updateInfoDisplay();
    }

    function gameDraw() { ctx.clearRect(0, 0, canvas.width, canvas.height); characters.forEach(char => { if (char) char.draw(ctx); }); }
    function gameLoop() { if (assetsLoading && characters.length === 0) { gameLoopRequestId = requestAnimationFrame(gameLoop); return; } gameUpdate(); gameDraw(); gameLoopRequestId = requestAnimationFrame(gameLoop); }

    function updateInfoDisplay() {
        const activeChar = getActiveCharacter();
        if (!activeChar) return;
        charModelNameDisplay.textContent = activeChar.id;
        charPosDisplay.textContent = `X=${Math.round(activeChar.x)}, Y=${Math.round(activeChar.y)}`;
        charAngleDegreesDisplay.textContent = `${Math.round(activeChar.facingAngleDegrees)}°`;
        charAngleIndexDisplay.textContent = activeChar.currentAngleIndex;
        const currentAnimInfo = activeChar.animations[activeChar.currentAnimationName];
        charAnimFrameDisplay.textContent = currentAnimInfo ? currentAnimInfo.currentFrameIndex : 'N/A';

        let statusText = activeChar.currentAnimationName.toUpperCase();
        if (activeChar.isFlying) {
            statusText = "FLYING (Roll Anim)";
        } else if (activeChar.isDancing) {
            statusText = "DANCING";
        }
        charStatusDisplay.textContent = statusText;

        movementLockStatusDisplay.textContent = globalMovementLocked ? "YES" : "NO";
        if(movementSpeedInput) movementSpeedValueDisplay.textContent = parseFloat(activeChar.baseMovementSpeed).toFixed(1);
        if(animationSpeedInput) animationSpeedValueDisplay.textContent = parseFloat(animationSpeedInput.value).toFixed(2);
    }

    modelSelectDropdown.addEventListener('change', (e) => {
        activeCharacterId = e.target.value;
        const newActiveChar = getActiveCharacter();
        if (newActiveChar) {
            lastMouseAngleDegrees = newActiveChar.facingAngleDegrees;
            animationSpeedInput.value = newActiveChar.animationSpeed;
            movementSpeedInput.value = newActiveChar.baseMovementSpeed;
        }
        updateInfoDisplay();
    });
    nextModelBtn.addEventListener('click', () => {
        if (characters.length > 0) {
            const currentIndex = characters.findIndex(char => char.id === activeCharacterId);
            const nextIdx = (currentIndex + 1) % characters.length;
            activeCharacterId = characters[nextIdx].id;
            modelSelectDropdown.value = activeCharacterId;
            const newActiveChar = getActiveCharacter();
            if (newActiveChar) {
                lastMouseAngleDegrees = newActiveChar.facingAngleDegrees;
                animationSpeedInput.value = newActiveChar.animationSpeed;
                movementSpeedInput.value = newActiveChar.baseMovementSpeed;
            }
            updateInfoDisplay();
        }
    });
    toggleParticlesBtn.addEventListener('click', () => { globalParticlesEnabled = !globalParticlesEnabled; toggleParticlesBtn.textContent = `Dust Particles: ${globalParticlesEnabled ? 'ON' : 'OFF'}`; });
    toggleMovementLockBtn.addEventListener('click', () => { globalMovementLocked = !globalMovementLocked; toggleMovementLockBtn.textContent = `Movement: ${globalMovementLocked ? 'LOCKED' : 'ACTIVE'}`; updateInfoDisplay(); });
    animationSpeedInput.addEventListener('input', (e) => { const speed = parseFloat(e.target.value); characters.forEach(char => { if(char) char.animationSpeed = speed; }); animationSpeedValueDisplay.textContent = speed.toFixed(2); });
    if(animationSpeedInput) animationSpeedValueDisplay.textContent = parseFloat(animationSpeedInput.value).toFixed(2);

    movementSpeedInput.addEventListener('input', (e) => {
        const newBaseSpeed = parseFloat(e.target.value);
        movementSpeedValueDisplay.textContent = newBaseSpeed.toFixed(1);
        const activeChar = getActiveCharacter();
        if (activeChar) {
            activeChar.baseMovementSpeed = newBaseSpeed;
            activeChar.movementSpeed = activeChar.isFlying ? newBaseSpeed * activeChar.flySpeedFactor : newBaseSpeed;
        } else {
             characters.forEach(char => { if(char) { char.baseMovementSpeed = newBaseSpeed; char.movementSpeed = char.isFlying ? newBaseSpeed * char.flySpeedFactor : newBaseSpeed; }});
        }
    });
    if(movementSpeedInput) movementSpeedValueDisplay.textContent = parseFloat(movementSpeedInput.value).toFixed(1);

    window.addEventListener('keydown', (e) => {
        const key = e.key.toLowerCase();
        if (key === 'shift') keys.Shift = true;
        else if (key === 'r') {
            if (!keys.r) {
                rKeyJustPressed = true;
            }
            keys.r = true;
        }
        else if (keys.hasOwnProperty(key)) keys[key] = true;

        if (["arrowup", "arrowdown", "arrowleft", "arrowright", " ", "shift", "r"].includes(key)) {
            e.preventDefault();
        }
    });

    window.addEventListener('keyup', (e) => {
        const key = e.key.toLowerCase();
        if (key === 'shift') keys.Shift = false;
        else if (key === 'r') keys.r = false;
        else if (keys.hasOwnProperty(key)) keys[key] = false;
    });

    canvas.addEventListener('mouseenter', () => { isMouseOverCanvas = true; });
    canvas.addEventListener('mouseleave', () => { isMouseOverCanvas = false; });
    canvas.addEventListener('mousemove', (e) => {
        const activeChar = getActiveCharacter();
        if (!activeChar || !canvas) return;
        const rect = canvas.getBoundingClientRect();
        const mouseXInCanvas = e.clientX - rect.left;
        const mouseYInCanvas = e.clientY - rect.top;
        const dx_mouse = mouseXInCanvas - activeChar.x;
        const dy_mouse = mouseYInCanvas - activeChar.y;
        lastMouseAngleDegrees = (Math.atan2(dy_mouse, dx_mouse) * (180 / Math.PI) + 360) % 360;
    });

    loadGameAssets();
});